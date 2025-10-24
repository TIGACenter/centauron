import io
import json
import logging
import mimetypes
import uuid
from typing import Any

import httpx
import requests
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import QuerySet
from django.http import Http404, HttpResponse, StreamingHttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from django.views import View
from django.views.generic import TemplateView

from apps.challenge.challenge_dataset.models import EvaluationCode
from apps.challenge.challenge_submission.models import Submission, SubmissionStatus, SubmissionToNodes
from apps.challenge.challenge_submission.tasks import send_results_to_submission_submitter, export_artifacts, \
    send_aggregated_submission_to_submitter
from apps.challenge.models import Challenge
from apps.challenge.views import BaseTabView
from apps.computing.computing_artifact.models import ComputingJobArtifact
from apps.computing.computing_executions.backend.k8s.tasks import get_auth_token
from apps.computing.computing_executions.models import ComputingJobExecution
from apps.computing.models import ComputingJobDefinition
from apps.computing.tasks import start_task_from_computing_execution
import pandas as pd

from apps.storage.models import File
from apps.storage.storage_importer.models import ImportFolder
from apps.storage.storage_importer.tasks import import_single_file


class ListView(BaseTabView):
    template_name = 'challenge/challenge_submission/tab.html'

    def get_tab_name(self):
        return 'submissions'


class DetailView(LoginRequiredMixin, TemplateView):
    template_name = 'challenge/challenge_submission/detail.html'

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        challenge_pk = self.kwargs.get('pk')
        object = get_object_or_404(Submission, challenge_id=challenge_pk, pk=self.kwargs.get('submission_pk'))
        cjd = self.request.GET.get('cjd', None)
        if cjd is not None:
            definition = get_object_or_404(ComputingJobDefinition,
                                           pk=cjd)  # TODO , submission__challenge_id=challenge_pk)
        else:
            definition = object.computing_pipeline.stages.first()
        cje = self.request.GET.get('cje', None)
        execution = None
        origin = self.request.user.profile
        if cje is not None and definition is not None:
            execution = get_object_or_404(ComputingJobExecution, pk=cje, created_by=origin, definition=definition)
        elif cje is None and definition is not None:
            execution = definition.executions.filter(created_by=origin).order_by('-date_created').first()

        if definition.is_batched:
            order_by = 'batch_number'
        else:
            order_by = '-date_created'
        executions = definition.executions.filter(created_by=origin).order_by(order_by)

        ground_truth = None
        if definition.is_label_crossing_job:
            ground_truth = EvaluationCode.objects.get_by_identifier(
                definition.entrypoint).schema.ground_truths.order_by('-date_created').first()

        stages = object.computing_pipeline.stages.order_by('position')
        challenge = Challenge.objects.get(pk=challenge_pk)
        has_data_from_multiple_nodes = challenge.has_multiple_data_origins
        sendable = object.submissiontonodes_set.exclude(status=SubmissionToNodes.Status.RESULTS).count() == 0
        # this exists if the submitter submitted a submission on the same node as the challenge owner created the challenge.
        part_submission_on_same_node = Submission.objects.filter(reference=object.identifier).first()

        if execution is not None:
            execution = executions.first()

        ctx.update({
            'part_submission_on_same_node': part_submission_on_same_node,
            'challenge': challenge,
            'submission_status': SubmissionStatus.Status,
            'ground_truth': ground_truth,
            'object': object,
            'pipeline': object.computing_pipeline,
            'execution': execution,
            'definition': definition,
            'executions': executions,
            'batch_view': definition.is_batched,
            'stages': stages,
            'has_data_from_multiple_nodes': has_data_from_multiple_nodes,
            'submission_nodes': object.submissiontonodes_set.all(),
            'sendable': sendable
        })
        if execution is not None:
            ctx['refresh_page'] = execution.definition.execution_type_is_auto and (
                execution.is_running or execution.is_pending or execution.is_created or execution.is_creating or execution.is_preparing)
        return ctx

    def post(self, request, **kwargs):
        submission_pk = self.kwargs.get('submission_pk')
        challenge_pk = self.kwargs.get('pk')
        execution_pk = self.kwargs.get('execution_pk', None)
        submission = get_object_or_404(Submission, challenge_id=challenge_pk, pk=submission_pk)

        # start the whole job
        if 'run_computing_job' in request.POST:
            transaction.on_commit(lambda: submission.computing_pipeline.execute(self.request.user.profile.id_as_str,
                                                                                submission_pk=submission.pk))
        # start only a single cjd
        if 'run_computing_definition' in request.POST:
            computing_definition_pk = request.POST.get('computing_definition', None)
            definition = ComputingJobDefinition.objects.get(pk=computing_definition_pk)  # TODO get by project as well
            # TODO only restart the selected definition
            if definition.is_batched:
                # only restart batch and not whole job
                start_task_from_computing_execution.delay(self.request.user.profile.id_as_str, execution_pk)
            else:
                # TODO add the submission id to execute. then add the CJEs to the submission
                transaction.on_commit(lambda:
                                      ComputingJobDefinition.objects.get(pk=computing_definition_pk).execute(
                                          self.request.user.profile.pk,
                                          submission.pk))

        return redirect('challenge:challenge_submission:detail', pk=challenge_pk, submission_pk=submission_pk)


class SubmissionSendPartialLogView(LoginRequiredMixin, TemplateView):
    template_name = 'challenge/challenge_submission/send_partial_log.html'

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        execution_pk = self.kwargs.get('execution_pk')
        current_execution = ComputingJobExecution.objects.get(pk=execution_pk) # TODO add challenge
        ctx['e'] = current_execution
        ctx['logs'] = current_execution.log_entries.all()
        return ctx

class SubmissionSendPartialArtefactsView(LoginRequiredMixin, TemplateView):
    template_name = 'challenge/challenge_submission/send_partial_artefacts.html'

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        execution_pk = self.kwargs.get('execution_pk')
        current_execution = ComputingJobExecution.objects.get(pk=execution_pk) # TODO add challenge
        ctx['e'] = current_execution
        ctx['artefacts'] = current_execution.artifacts.all()
        return ctx

class SubmissionSendAggregatedView(LoginRequiredMixin, TemplateView):
    template_name = 'challenge/challenge_submission/send_aggregated.html'

    def calculate_average_metrics(self, result_files):
        cache = []
        metrics = []
        for p in result_files:
            if p.identifier in cache:
                continue
            cache.append(p.identifier)
            artefacts_qs:ComputingJobArtifact|None = p.artifacts.filter(file__name="results.json").first()
            if artefacts_qs is not None:
                if artefacts_qs.file.as_path is not None and artefacts_qs.file.as_path.exists():
                    with artefacts_qs.file.as_path.open() as f:
                        j = json.load(f)
                        metrics.append(j)

        df = pd.DataFrame(metrics)
        avg = df.mean()
        avg_metrics = avg.to_dict()
        return avg_metrics

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        challenge_pk = self.kwargs.get('pk')
        definition_pk = self.kwargs.get('definition_pk')
        submission = get_object_or_404(Submission, challenge_id=challenge_pk, pk=self.kwargs.get('submission_pk'))
        submission_to_nodes = submission.submissiontonodes_set.all()

        posts:QuerySet[ComputingJobExecution] = submission.computing_job_executions.filter(definition__name=".post").order_by('-finished_at')
        avg_metrics = self.calculate_average_metrics(posts)

        ctx.update({
            'object': submission,
            'challenge': Challenge.objects.get(pk=challenge_pk),
            'submission_to_nodes': submission_to_nodes,
            'metrics': avg_metrics,
        })
        return ctx

    def post(self, request, *args, **kwargs):
        challenge_pk = self.kwargs.get('pk')
        definition_pk = self.kwargs.get('definition_pk')
        submission = get_object_or_404(Submission, challenge_id=challenge_pk, pk=self.kwargs.get('submission_pk'))
        submission_to_nodes = submission.submissiontonodes_set.all()
        posts:QuerySet[ComputingJobExecution] = submission.computing_job_executions.filter(definition__name=".post").order_by('-finished_at')
        avg_metrics = self.calculate_average_metrics(posts)
        cje = ComputingJobExecution.objects.create(definition=posts.first().definition,
                                             executed=True,
                                             status=ComputingJobExecution.Status.ACCEPTED,
                                             )

        import_folder = ImportFolder.create()
        path = 'results.json'
        file = File(
            name='results.json',
            import_folder=import_folder,
            original_filename='results.json',
            original_path='results.json',
            path=path
        )
        file.save()

        parent = settings.TMP_DIR / uuid.uuid4().hex
        parent.mkdir(parents=True, exist_ok=True)
        uuid__hex = parent / uuid.uuid4().hex
        with uuid__hex.open('w') as f:
            json.dump(avg_metrics, f)

        import_single_file(file, uuid__hex)

        ComputingJobArtifact.objects.create(
            computing_job=cje,
            file=file
        )
        submission.extract_target_metrics(cje)

        # send to submitter
        send_aggregated_submission_to_submitter.delay(submission.id_as_str, request.user.profile.id_as_str)

        messages.success(request, 'Submission results will be send to submitter.')

        return redirect('challenge:challenge_submission:send-aggregated', pk=challenge_pk, submission_pk=submission.pk)


class SubmissionSendView(LoginRequiredMixin, TemplateView):
    template_name = 'challenge/challenge_submission/send.html'

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        challenge_pk = self.kwargs.get('pk')
        definition_pk = self.kwargs.get('definition_pk')
        execution_pk = self.kwargs.get('execution_pk')
        object = get_object_or_404(Submission, challenge_id=challenge_pk, pk=self.kwargs.get('submission_pk'))

        current_execution = ComputingJobExecution.objects.get(pk=execution_pk)
        # all_stages = sorted(self.get_execution_before(current_execution), key=lambda e: e.definition.position)
        all_stages = current_execution.definition.pipeline.stages.order_by('position')

        # TODO create a dict of all artefacts of all stages of all submission to nodes
        # sth like this: [stage: [artefacts]]
        # stages have different identifiers, so it must be pooled somehow.
        # only use the artefacts

        artefacts_per_execution = {}
        artefacts = ComputingJobArtifact.objects.filter(
            pk__in=object.computing_job_executions.distinct().values_list('artifacts', flat=True).distinct()).exclude(
            origin=self.request.user.profile)
        for a in artefacts:
            if a.computing_job.identifier not in list(map(lambda e: e.identifier, artefacts_per_execution.keys())):
                artefacts_per_execution[a.computing_job] = []
            key = None
            for k in artefacts_per_execution.keys():
                if k.identifier == a.computing_job.identifier:
                    key = k
                    break
            artefacts_per_execution[key].append(a)

        ctx.update({
            'object': object,
            'challenge': Challenge.objects.get(pk=challenge_pk),
            'definition': ComputingJobDefinition.objects.get(pk=definition_pk),
            'execution': current_execution,
            'all_stages': all_stages,
            'artefacts_per_execution': artefacts
        })
        return ctx

    def get_execution_before(self, exec):
        arr = []
        return exec.definition.pipeline.stages.order_by('position')
        # i = exec
        # while i is not None:
        #     arr.append(i)
        #     # if i.executed_after.first() is not None:
        #     i = i.executed_after.first()
        #     # if i.executed_before is None and i.executed_after.count() > 0:
        #     #     i = i.executed_after.first()
        #     # else:
        #     #     i = i.executed_before
        #
        # return arr

    def post(self, request, **kwargs):
        challenge_pk = self.kwargs.get('pk')
        definition_pk = self.kwargs.get('definition_pk')
        execution_pk = self.kwargs.get('execution_pk')
        submission_pk = self.kwargs.get('submission_pk')
        messages.success(request, 'Submission results will be sent to submitter shortly.')

        checked_logs = request.POST.getlist('log', [])  # format: {{ execution.pk }}.{{ log.pk }}
        checked_artefacts = request.POST.getlist('artefact', [])  # format: {{ execution.pk }}.{{ artefact.pk }}
        send_results_to_submission_submitter.delay(
            request.user.profile.id_as_str,
            challenge_pk,
            definition_pk,
            submission_pk,
            checked_logs,
            checked_artefacts,
        execution_pk=execution_pk)
        return redirect('challenge:challenge_submission:send', pk=challenge_pk, definition_pk=definition_pk,
                        execution_pk=execution_pk, submission_pk=submission_pk)


class SubmissionManualTaskPyScriptEnvView(LoginRequiredMixin, View):

    def post(self, request, pk, submission_pk):
        job_execution_pk = request.GET.get('cje', None)
        if job_execution_pk is None:
            raise Http404()
        submission = Submission.objects.get(pk=submission_pk, challenge_id=pk)
        execution = ComputingJobExecution.objects.get(pk=job_execution_pk)  # TODO add challenge or user or so
        code = EvaluationCode.objects.get_by_identifier(execution.definition.entrypoint)
        # execution.definition.previous().
        processing_results = {}
        if len(execution.definition.input) > 0:
            input_file_name = execution.definition.input[0]
            stage, pattern = input_file_name.split(':')
            if pattern == '*': pattern = '(.*?)'
            stage_with_artifact: ComputingJobDefinition = execution.definition.pipeline.stages.filter(
                name=stage).first()
            # TODO this must be also specific for the computingjobexecution if there are multiple job executions
            artifacts_filter = stage_with_artifact.executions.order_by('-date_created').first().artifacts.filter(
                file__name__iregex=pattern)
            if artifacts_filter is not None:
                for a in artifacts_filter:
                    processing_results[a.file.original_path] = reverse(
                        "challenge:challenge_submission:download-artifact",
                        kwargs=dict(pk=pk, submission_pk=submission_pk, artifact_pk=a.pk))
                # # file = settings.COMPUTING_K8S_DATA_DIRECTORY / f.file.path.path
                # with artifacts_filter.file.as_path.open() as fd:
                #     processing_results = fd.read()

        ctx = {
            'object': submission,
            'execution': execution,
            'code': code,
            'processing_results': processing_results
        }

        return render(request, 'challenge/challenge_submission/partials/pyscript_env.html', ctx)




class DownloadArtifactView(LoginRequiredMixin, View):

    def get(self, request, pk, submission_pk, artifact_pk):
        # artifact = SubmissionArtefact.objects.get(submission=submission_pk, pk=artifact_pk, submission_challenge_id=pk)
        # FIXME
        # artifact = SubmissionArtefact.objects.get(artefact__computing_job__definition__pipeline__submission_id=submission_pk,
        #                                           artefact_id=artifact_pk,
        #                                           artefact__computing_job__definition__pipeline__submission__challenge_id=pk)
        artifact = get_object_or_404(ComputingJobArtifact, pk=artifact_pk)
        p = artifact.file.as_path
        content = ''
        content_type = "text/plain"
        if p is not None:
            content_type = artifact.file.content_type
            # reading everything as string utf-8. this is not suitable for binary files nor images
            with p.open('rb') as f:
                content = f.read()

        return HttpResponse(content, content_type=content_type)


class SubmissionManualTaskPyScriptEnvStoreResultsView(LoginRequiredMixin, View):

    def post(self, request, pk, submission_pk):
        job_execution_pk = request.GET.get('cje', None)
        content = request.POST.get('result')

        if job_execution_pk is None:
            raise Http404()
        submission = Submission.objects.get(pk=submission_pk)
        execution = ComputingJobExecution.objects.get(pk=job_execution_pk)  # TODO add challenge or user or so
        # only single file permitted here
        filename = execution.definition.output[0]
        execution.artifact_path.mkdir(exist_ok=True)
        output_dir = execution.artifact_path / filename
        with output_dir.open('w') as f:
            f.write(content)

        if not execution.is_success:
            # import the artefact file.
            # first register the file, then import
            # register file
            token = get_auth_token(request.user.profile)
            headers = {'Authorization': f'Token {token}'}
            url = settings.ADDRESS + reverse('api-storage-create') + '?return=identifiers'
            with io.BytesIO() as buffer:
                buffer.write(b'name,original_path,content_type,size,src\n')
                content_type = mimetypes.guess_type(output_dir)[0]
                row = f'{filename},{filename},{content_type},{output_dir.stat().st_size},'
                buffer.write(row.encode('UTF-8'))
                buffer.seek(0)
                r = httpx.post(url, files={'file': buffer}, headers=headers)
                if r.status_code != 201:
                    messages.error(request, f'API responded with status code: {r.status_code}, {r.text}')
                    logging.error('%s %s', r.status_code, r.text)
                    return redirect(request.META['HTTP_REFERER'])

                file_id = r.json()[0]
            # import the artefact file. use artefact importer and its api.
            url = settings.ADDRESS + reverse('computing:computing_execution:api-artifact',
                                             kwargs=dict(pk=execution.id_as_str))
            # payload = {
            #     'original_path': filename,
            #     'original_file_name': filename,
            #     'file': filename,
            # }
            payload = [file_id]

            response = requests.post(url, json=payload, headers=headers)
            if response.status_code == 200:
                status = ComputingJobExecution.Status.SUCCESS
                messages.success(request, 'Results stored.')
            else:
                status = ComputingJobExecution.Status.ERROR
                logging.error("%s %s", response.status_code, response.text)
                messages.error(request, 'Could not import results (maybe the artefact already exists?).')

            url = settings.ADDRESS + reverse('computing:computing_execution:api-stage',
                                             kwargs=dict(pk=execution.id_as_str))
            payload = {'status': status}
            response = requests.post(url, payload, headers=headers)
            if response.status_code == 200:
                messages.success(request, 'state set successfully to ' + status)
            else:
                messages.error(request, 'error setting state to ' + status)
        else:
            messages.error(request, 'Cannot store result as job is already state = success.')

        url = reverse('challenge:challenge_submission:detail',
                      kwargs=dict(pk=pk, submission_pk=submission_pk)) + f'?cjd={execution.definition_id}'
        return redirect(url)


class DistributeSubmissionView(LoginRequiredMixin, View):

    def post(self, request, pk, submission_pk, *args, **kwargs):
        submission = Challenge.objects.get(pk=pk).submissions.get(pk=submission_pk)
        submission.distribute_to_nodes()
        messages.success(request, 'Submission will be distributed to other data owners.')
        return redirect('challenge:challenge_submission:detail', pk=pk, submission_pk=submission_pk)


class ExportArtifactsView(LoginRequiredMixin, View):

    def post(self, request, pk, submission_pk, execution_pk, **kwargs):
        execution = ComputingJobExecution.objects.get(pk=execution_pk)
        path = f'{slugify(execution.definition.name)}-{timezone.now()}'
        transaction.on_commit(lambda: export_artifacts.delay(execution_pk, path))
        messages.success(request, f'Artifacts will be exported to {path}')
        return redirect('challenge:challenge_submission:detail', pk=pk, submission_pk=submission_pk)

class ExportLogView(LoginRequiredMixin, View):

    def get(self, request, pk, submission_pk, execution_pk, **kwargs):
        execution = ComputingJobExecution.objects.get(pk=execution_pk)
        return StreamingHttpResponse(
            (f'[{log.logged_at}] {log.content}' for log in execution.get_log()),
            content_type="text/plain",
            headers={
                "Content-Disposition": f'attachment; filename="{execution.definition.name}.log"'},
        )

