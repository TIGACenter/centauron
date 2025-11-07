import csv
import datetime
import itertools
import json
import logging
import random
from functools import partial
from json import JSONDecodeError
from typing import Any, Dict
from uuid import UUID

import httpx
from celery import chain
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import Sum, Q
from django.http import StreamingHttpResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView, DetailView as DjangoDetailView, FormView
from slugify import slugify

from apps.auth.keycloak import refresh_jwt
from apps.blockchain.models import Log
from apps.challenge.challenge_submission.models import Submission
from apps.computing.utils import _generate_random_name
from apps.core import identifier
from apps.federation.federation_invitation.models import FederationInvitation
from apps.federation.file_transfer.models import TransferJob, TransferItem
from apps.permission.models import Permission
from apps.project.forms import SendDataToAnnotatorForm, CreateProjectForm
from apps.project.models import Project, DataView
from apps.project.project_ground_truth.models import GroundTruth
from apps.project.tasks import create_transfer_items_for_share, create_transfer_job_and_start
from apps.share.models import Share
from apps.share.tasks import create_share, retract_share
from apps.storage.models import File
from apps.terminology.models import CodeSet, Code
from apps.terminology.views import TerminologyDialogAddView
from apps.utils import get_node_origin

User = get_user_model()


class ProjectContextMixin:

    def get_project_id(self) -> UUID | None:
        return self.kwargs.get('pk')

    def get_project(self) -> Project:
        return Project.objects.for_user(self.request.user.profile).get(pk=self.get_project_id())

    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        ctx['project'] = self.get_project()
        return ctx


class ListView(LoginRequiredMixin, TemplateView):
    template_name = 'project/list.html'

    def get_context_data(self, **kwargs):
        user_profile = self.request.user.profile
        qs_created = Project.objects.filter(created_by=user_profile)
        qs_invited = Project.objects.for_user(user_profile) \
            .filter(members__invite__status=FederationInvitation.Status.ACCEPTED)
        return {
            'projects': qs_created.union(qs_invited).order_by('-date_created')
        }


class DetailView(LoginRequiredMixin, View):

    def get(self, request, pk):
        project = Project.objects.for_user(self.request.user.profile).get(pk=pk)
        # if no view exists yet, create one.
        view = project.views.first()
        if view is None:
            dt_config = """
            [{
          "data": "name",
          "title": "Name",
          render: (data, type, row, meta) => {
            console.log(row)
            if (row.imported) {
              return `<strong><a href="${row.href}">${data}</a></strong>`
            }
            return data;
          }
         },
          {
            "data": "date_created",
            "title": "Created at",
            render: DataTable.render.datetime()
          },
          {
            "data": "origin.human_readable",
            name: 'origin__human_readable',
            "title": "Origin"
          },
          {
            data: 'case',
            title: 'Case'
          },
          {data: 'terms', title: 'Terms'},
          {data: 'studies', title: 'Local Cohort'}
        ]"""
            view = DataView.objects.create(created_by=request.user.profile,
                                           project=project,
                                           name='Files',
                                           datatable_config=dt_config,
                                           model=DataView.Model.FILE)
            # TODO also create the DataView for case

        return redirect('project:detail-view', pk=project.pk, view_pk=view.pk)


class CreateShareQueryView(LoginRequiredMixin, ProjectContextMixin, DjangoDetailView):
    template_name = 'project/share/query.html'

    def get_queryset(self):
        return Project.objects.all()

    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        codes = []
        project_ :Project= ctx['project']
        codeset = project_.codeset
        if codeset is not None:
            for c in project_.codeset.codes.all():
                codes.append({
                    'id': c.id_as_str,
                    'code': c.code,
                    'codesystem_name': c.codesystem_name,
                })
        ctx['codes'] = codes
        schema = project_.latest_ground_truth_schema
        if schema is None:
            ctx['project_has_ground_truth_schema'] = False
        else:
            ctx['project_has_ground_truth_schema'] = True
            ctx['project_has_ground_truth'] = schema.ground_truths.exists()
        return ctx


class CreateShareQueryActionView(LoginRequiredMixin, ProjectContextMixin, View):

    def post(self, request, pk, **kwargs):
        project = self.get_project()
        query = request.POST.dict().get('query')
        try:
            query_parsed = json.loads(query)
        except JSONDecodeError as e:
            return render(request, 'project/share/query-error.html', {'error': str(e)})

        gt_schema = project.latest_ground_truth_schema
        if gt_schema is not None:
            ground_truth = gt_schema.ground_truths.filter(created_by=request.user.profile).order_by(
                '-date_created').first()
        else:
            ground_truth = None

        members = project.members.exclude(
            user=request.user.profile
        )

        # TODO this will fail after a certain amount of shares per project and user
        def generate_name(n):
            qs = Share.objects.filter(name=n, project=project, created_by=request.user.profile)
            if qs.exists():
                return generate_name(_generate_random_name())
            return n

        qs = self.get_project().cases.filter(**query_parsed)
        terms = Code.objects.filter(pk__in=qs.values_list('files__codes__pk', flat=True).distinct())
        # TODO add: user has permission to share
        extra_data_applications = project.extra_data_for_user(request.user.profile).values_list('application_identifier', flat=True).distinct()
        logging.info(extra_data_applications)
        ctx = {
            'project': project,
            'members': members,
            'codes': terms,
            'total': qs.count(),
            'query': query,
            'csv_schema': gt_schema,
            'ground_truth': ground_truth,
            'share_name': generate_name(_generate_random_name()),
            'shares': self.get_project().shares.filter(created_by=request.user.profile).order_by('-date_created'),
            'extra_data_applications': extra_data_applications
        }
        return render(request, 'project/share/query-result.html', ctx)

class CreateShareActionQueryFilterView(LoginRequiredMixin, ProjectContextMixin, View):

    def post(self, request, pk, **kwargs):
        key = 'csvfile'
        if key not in request.FILES:
            return JsonResponse({'error': 'No file selected'}, status=400)

        uploaded_file = request.FILES[key]

        if not uploaded_file.name.endswith('.csv'):
            return JsonResponse({'error': 'Only CSV files are allowed'}, status=400)

        try:
            # Parse the CSV file
            decoded_file = uploaded_file.read().decode('utf-8').splitlines()
            reader = csv.DictReader(decoded_file)

            # Check if 'id' column exists
            if 'id' not in reader.fieldnames:
                return JsonResponse({'error': "'id' column not found in the CSV file"}, status=400)

            # Read all values from the 'id' column
            id_list = [row['id'] for row in reader if row['id']]
            request.session['create_share_file_id_list'] = id_list
            # return JsonResponse({'message': 'File processed successfully', 'ids': id_list})
        except csv.Error as e:
            return JsonResponse({'error': f'Error processing CSV file: {str(e)}'}, status=400)
        except Exception as e:
            return JsonResponse({'error': f'Unexpected error: {str(e)}'}, status=500)

        # only query the files and cases for which the user is the origin i.e. the user has the ground truth.
        # if only extradata e.g. annotations are shared, the user has probably no ground truth.
        project = self.get_project()
        # qs = project.files.filter(id__in=id_list, origin=request.user.profile)
        # only files that are imported for the user
        # TODO filter for only files that the user has the permission to share
        qs = project.files_for_user(request.user.profile).filter(id__in=id_list, origin=request.user.profile)
        qs_cases = qs.values_list('case', flat=True).distinct()
        ed = project.extra_data_for_user(request.user.profile).filter(application_identifier__in=request.POST.getlist('extra_data_applications'), file_id__in=id_list)
        ctx = {
            "files": qs,
            'cases': qs_cases,
            'actions': [e.value for e in Permission.Action],
            'csv_schema': project.latest_ground_truth_schema,
            'ground_truth': project.latest_ground_truth_schema.ground_truths.first(),
            'extra_data': ed,
            'total': qs.count(),
            'total_extra_data': ed.count(),
            'project': self.get_project(),
        }
        return render(request, 'project/share/query-results-filter.html', ctx)


class CreateShareActionUploadCSV(LoginRequiredMixin, ProjectContextMixin, View):

    def post(self, request, pk, **kwargs):
        ctx = {}
        if 'file' in request.FILES:
            uploaded_file = request.FILES['file']
        return render(request, 'project/share/upload.html', ctx)


class CreateShareActionView(LoginRequiredMixin, ProjectContextMixin, View):

    def post(self, request, pk, **kwargs):
        data = request.POST.dict()
        nodes = request.POST.getlist('nodes')
        share_name = data.get('share_name', 'Share')
        # checked_cases = request.POST.getlist('cases')
        files = request.POST.getlist('file', [])
        checked_actions = request.POST.getlist('actions', [])
        checked_term_filter = request.POST.getlist('codes-filter', [])

        # checked_files = request.POST.getlist('files')
        percentage = int(data.get('percentage', '100'))
        # all_cases_checked = data.get('cases_all', 'off') == 'on'
        query = data.get('query', {})
        terms = request.POST.getlist('codes', [])
        project = self.get_project()
        extra_data_applications = request.POST.getlist('extra_data_applications', [])
        retract_share_pk = data.get('retract_share')
        if retract_share_pk == 'null': retract_share_pk = None

        if len(nodes) == 0:
            messages.error(request, 'No nodes selected.')
            return redirect('project:create-share-query', pk=project.pk)

        # if all_cases_checked:
        # qs_codes = Code.objects.filter(pk__in=checked_term_filter)
        #     checked_cases = list(
        #         project.cases.filter(**json.loads(query), files__codes__in=qs_codes).values_list('pk', flat=True))

        key_initial_file_id_list = 'create_share_file_id_list'
        initial_file_id_list = request.session.get(key_initial_file_id_list)
        ed = project.extra_data_for_user(request.user.profile).filter(application_identifier__in=extra_data_applications, file_id__in=initial_file_id_list).count()
        del request.session[key_initial_file_id_list]

        if len(files) == 0 and ed == 0:
            messages.error(request, 'No cases or extra data selected.')
            return redirect('project:create-share-query', pk=project.pk)

        if len(share_name.strip()) == 0:
            share_name = 'Share'

        valid_from = timezone.now()
        valid_until = timezone.now() + datetime.timedelta(
            days=30)  # TODO make valid_until configurable via user interface
        # TODO check that permissions is of items from Permission.Action
        # TODO map actions to Permission.Actions for security reasons.
        current_user = request.user.profile
        if len(files) > 0:
            gt = project.latest_ground_truth_schema.ground_truths.first()
        else:
            gt = None
        share = Share.objects.create(origin=current_user, created_by=current_user, name=share_name, project=project)

        # first execute retract share and then create share
        # retract previous share
        celery_task_chain = []
        if retract_share_pk is not None:
            celery_task_chain.append(retract_share.s(retract_share_pk))

        celery_task_chain.append(create_share.s('file',
                                                project.identifier,
                                                valid_from=valid_from,
                                                valid_until=valid_until,
                                                created_by_pk=current_user.id_as_str,
                                                target_nodes_pk=nodes,
                                                query=query,
                                                percentage=percentage,
                                                allowed_actions=checked_actions,
                                                share_name=share_name,
                                                file_pks=files,
                                                project_pk=self.get_project_id(),
                                                term_pks=terms,
                                                share_pk=share.id_as_str,
                                                extra_data_applications=extra_data_applications,
                                                initial_file_list_id=initial_file_id_list,
                                                ground_truth_pk=gt.id_as_str if gt is not None else None))
        transaction.on_commit(lambda: chain(*celery_task_chain)())

        messages.success(request, 'Share will be sent to selected nodes.')
        return redirect('project:share-detail', pk=project.pk, share_pk=share.pk)


class DataSharedWithMeView(LoginRequiredMixin, TemplateView):
    template_name = 'project/shared_with_me.html'

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        ctx.update({
            'shares': Share.objects.filter(created_by=self.request.user.profile)
        })
        return ctx

    def post(self, request, **kwargs):
        share_pk = request.POST.get('share_pk')
        share = Share.objects.filter(created_by=self.request.user.profile, pk=share_pk).first()
        create_transfer_items_for_share.delay(self.request.user.profile.id_as_str, share_pk)
        messages.success(request, f'Share {share.name} will be downloaded in background.')
        return redirect('project:data-shared-with-me')


class InvitesView(LoginRequiredMixin, TemplateView):
    template_name = 'project/invites.html'

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        ctx['invites'] = FederationInvitation.objects \
            .filter(to=self.request.user.profile, status=FederationInvitation.Status.OPEN).order_by('-date_created')

        return ctx


class DeleteCollaboratorActionView(LoginRequiredMixin, View):

    def post(self, request, pk, **kwargs):
        # TODO check if current user is project owner
        project = get_object_or_404(Project, pk=pk)
        project.remove_member(request.user.profile, request.POST.dict().get('member'))
        messages.success(request, 'Collaborator removed from project.')
        return redirect('project:collaborator-list', pk=pk)


class ViewView(LoginRequiredMixin, DjangoDetailView):
    template_name = 'project/detail.html'

    def get_queryset(self):
        return Project.objects.for_user(self.request.user.profile)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        project = ctx['object']
        current_view_pk = self.kwargs.get('view_pk', None)
        if current_view_pk is not None:
            current_view = project.views.get(pk=current_view_pk)
        else:
            current_view = project.views.first()
        ctx.update({
            'cases': project.cases.all(),
            'views': project.views.all(),
            'current_view': current_view,
            # TODO select only challenges here to which the user is enrolled
            'challenges': project.challenges.all()
        })
        return ctx


class TerminologyListView(LoginRequiredMixin, ProjectContextMixin, TemplateView):
    template_name = 'project/terminology-list.html'

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        project = ctx['project']
        if project.codeset:
            ctx['codes'] = project.codeset.codes.all()
        return ctx


class TerminologyAddDialog(TerminologyDialogAddView):
    def get_action_url(self):
        return reverse('project:terminology-dialog-add', kwargs=self.kwargs)

    def form_valid(self, form):
        project = Project.objects.for_user(self.request.user.profile).get(pk=self.kwargs.get('pk'))
        code_id = form.cleaned_data['code_id']
        if project.codeset is None:
            project.codeset = CodeSet.objects.create()
            project.save(update_fields=['codeset'])
        # TODO add created_by to query
        project.codeset.codes.add(Code.objects.get(pk=code_id))
        messages.success(self.request, 'Code added to project.')
        return redirect(self.request.META['HTTP_REFERER'])

    def form_invalid(self, form):
        pass


class TerminologyDeleteAction(LoginRequiredMixin, View):

    def post(self, request, pk):
        project = Project.objects.for_user(self.request.user.profile).get(pk=self.kwargs.get('pk'))
        code_id = request.POST.get('code_id')
        code = Code.objects.get(pk=code_id, codesets=project.codeset)
        project.codeset.codes.remove(code)
        messages.success(request, 'Code deleted from project.')
        return redirect(self.request.META['HTTP_REFERER'])


class SendFilesToAnnotatorView(LoginRequiredMixin, ProjectContextMixin, FormView):
    template_name = 'project/send_to_annotator.html'
    form_class = SendDataToAnnotatorForm

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['annotation_backend'] = settings.ANNOTATION_BACKEND_URL
        return ctx

    def get_form_kwargs(self) -> dict[str, Any]:
        ctx = super().get_form_kwargs()
        ctx['project'] = self.get_project()
        return ctx

    def get_initial(self) -> dict[str, Any]:
        ctx = {'query': '{}'}
        if settings.DEBUG:
            ctx['project_id'] = 'e6e9a45f-ece6-472a-ba95-594de44172e9'
            ctx['dataset_id'] = 'a4797458-3d45-49a5-86d5-6666b44df4a6'
        return ctx

    def form_valid(self, form):
        # TODO this give a very tight coupling between centauron and the annotation backend. think about ways how to break that up. for now however it works.
        project_id = form.cleaned_data['project_id']
        dataset_id = form.cleaned_data['dataset_id']
        try:
            query = json.loads(form.cleaned_data.get('query'))
            self.create_labels(project_id, form.cleaned_data['codes'])
            self.create_tasks(project_id, dataset_id, query)
            messages.success(self.request, 'Task imported into annotation backend.')
        except Exception as e:
            logging.exception(e)
            messages.error(self.request, str(e))

        return redirect('project:detail', pk=str(self.get_project_id()))

    def get_jwt(self):
        refreh_token = self.request.user.socialaccount_set.first().socialtoken_set.first().token_secret
        return refresh_jwt(refreh_token)

    def create_labels(self, project_id, codes):
        url = f'{settings.ANNOTATION_BACKEND_URL}projects/{project_id}/labels/'
        # iterate of codes and create labels. if 400 is returned, the label already exists, whatever, try to create them anyway
        jwt = self.get_jwt()
        headers = {'Authorization': f'Bearer {jwt}'}
        for code in codes:
            # TODO if label with this color already exists, then try again with other color.
            payload = {'name': code.human_readable,
                       'color': f"#{random.randint(0, 0xFFFFFF):06x}",
                       'extra_data': {'id': code.id_as_str, 'codesystem': code.codesystem_name, 'code': code.code,
                                      'type': 'polygon'}}
            response = httpx.post(url, json=payload, headers=headers)
            if response.status_code != 200:
                logging.warning(f'Annotation Backend response status code: {response.status_code}')

    def create_tasks(self, project_id, dataset_id, query):
        project = self.get_project()
        files = project.files.filter(imported=True, **query)
        jwt = self.get_jwt()
        headers = {'Authorization': f'Bearer {jwt}'}
        url = f'{settings.ANNOTATION_BACKEND_URL}projects/{project_id}/datasets/{dataset_id}/tasks/'
        for file in files:
            payload = {
                "name": file.name,
                "extra_data": {
                    "id": file.identifier,
                },
                "url": f"{settings.IIPSRV_URL}{file.path}",
            }
            response = httpx.post(url, headers=headers, json=payload)
            if response.status_code != 201:
                logging.warning(f'Creating annotation task response status code: {response.status_code}')
                logging.warning(response.text)


class CollaboratorListView(LoginRequiredMixin, ProjectContextMixin, TemplateView):
    template_name = 'project/collaborators.html'

    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        project = ctx['project']
        ctx['project_members'] = project.members.all().prefetch_related('user__node')
        return ctx


class ShareListView(LoginRequiredMixin, ProjectContextMixin, TemplateView):
    template_name = 'project/share/list.html'

    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        ctx['shares'] = ctx['project'].shares.filter(created_by=self.request.user.profile).order_by('-date_created')
        return ctx


class ShareMixin(ProjectContextMixin):
    def get_share_id(self):
        return self.kwargs.get('share_pk')

    def get_share_qs(self):
        return Share.objects.filter(pk=self.get_share_id())

    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        share = self.get_share_qs().get(project=ctx['project'])
        ctx['share'] = share
        return ctx


class ShareDetailView(LoginRequiredMixin, ShareMixin, TemplateView):
    template_name = 'project/share/detail.html'

    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        ctx['tokens'] = ctx['share'].tokens.all()
        return ctx


class ShareDetailActionView(LoginRequiredMixin, ShareMixin, View):

    def post(self, request, **kwargs):
        messages.success(request, 'Share will be retracted.')
        retract_share.delay(str(self.get_share_id()))
        return redirect('project:share-detail', pk=self.get_project_id(), share_pk=self.get_share_id())


class DownloadFilesActionView(LoginRequiredMixin, ProjectContextMixin, View):

    def post(self, request, pk, **kwargs):
        ctx = {'project': self.get_project()}
        data = request.POST.dict()
        project = self.get_project()
        raw_query = data.get('query', '{}')
        is_query = 'btn_query' in data
        if not is_query:
            raw_query = raw_query.encode('utf-8').decode('unicode_escape')
        query = json.loads(raw_query)
        files = project.files_for_user(self.request.user.profile).filter(imported=False, **query).exclude(origin__node=get_node_origin()).distinct()

        if is_query:
            # TODO only show the files that the user has permission for download
            ctx['files'] = files
            ctx['files_total'] = files.count()
            ctx['query'] = raw_query
            ctx['files_size'] = files.aggregate(size=Sum("size", default=-1))['size']
            return render(request, 'project/download-query.html', ctx)
        else:
            if 'id__in' not in query:
                values_list = list(files.values_list('id', flat=True))
                query['id__in'] = [str(e) for e in values_list]
            tj = TransferJob.objects.create(project=project, query=query, created_by=request.user.profile)
            transaction.on_commit(partial(create_transfer_job_and_start.delay, tj.id_as_str, query))
            messages.success(request, 'Data will be downloaded.')
            return redirect('project:transfer-job', pk=self.get_project_id(), job_pk=tj.pk)


class DownloadFilesView(LoginRequiredMixin, ProjectContextMixin, TemplateView):
    template_name = 'project/download.html'

    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        project = ctx['project']
        # files not imported and originating from different node.
        # TODO only show the files that the user has permission for download
        files = project.files_for_user(self.request.user.profile).filter(imported=False).exclude(origin__node=get_node_origin())
        ctx['files'] = files
        ctx['files_total'] = files.count()
        ctx['files_size'] = files.aggregate(size=Sum("size", default=-1))['size']
        return ctx


class TransferJobDetailView(LoginRequiredMixin, ProjectContextMixin, TemplateView):
    template_name = 'project/transfer_job.html'

    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        project = ctx['project']
        tj = project.transfer_jobs.get(pk=self.kwargs.get('job_pk'))
        ctx['transfer_job'] = tj
        ctx['items_count'] = tj.transfer_items.count()
        ctx['items_pending'] = tj.transfer_items.filter(status=TransferItem.Status.PENDING).count()
        ctx['items_error'] = tj.transfer_items.filter(status=TransferItem.Status.ERROR).count()
        ctx['items_active'] = tj.transfer_items.filter(status=TransferItem.Status.ACTIVE).count()
        ctx['items_complete'] = tj.transfer_items.filter(status=TransferItem.Status.COMPLETE).count()
        ctx['items_filesize'] = tj.transfer_items.aggregate(sum=Sum('file__size'))['sum']

        return ctx


class TransferJobListView(LoginRequiredMixin, ProjectContextMixin, TemplateView):
    template_name = 'project/transfer_job-list.html'

    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        project = ctx['project']
        ctx['items'] = project.transfer_jobs.all().order_by('-date_created')
        return ctx


class TransferJobDetailActionView(LoginRequiredMixin, ProjectContextMixin, View):
    def post(self, request, pk, job_pk, **kwargs):
        job = self.get_project().transfer_jobs.get(pk=job_pk)
        if 'restart' in request.POST:
            job.restart()
            messages.success(request, 'Transfer Job will be restartet.')
        if 'kill' in request.POST:
            job.kill()
            messages.success(request, 'Transfer Job killed.')
        return redirect('project:transfer-job', pk=pk, job_pk=job_pk)


class EventListView(LoginRequiredMixin, ProjectContextMixin, TemplateView):
    template_name = 'project/event_list.html'

    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        ctx['events'] = ctx['project'].event_contexts.order_by('-date_created')
        return ctx


class DashboardView(LoginRequiredMixin, ProjectContextMixin, TemplateView):
    template_name = 'project/dashboard.html'

    def get(self, request, **kwargs):
        # only render dashboard if the current user is the project owner
        if self.get_project().origin == request.user.profile:
            return super().get(request, **kwargs)
        else:
            return redirect('project:detail', pk=self.get_project_id())

    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        project = ctx['project']
        ctx['cases_total'] = project.cases.count()
        ctx['files_total'] = project.files.count()
        ctx['annotation_total'] = project.files.filter(
            extra_data__application_identifier=settings.ANNOTATION_BACKEND_APPLICATION_IDENTIFIER).count()
        ctx['challenges_total'] = project.challenges.count()
        ctx['challenge_submissions_total'] = 0  # TODO
        ctx['members'] = project.members.all()

        ctx['data_chart_file_distribution_by_nodes'] = self.get_data_chart_file_distribution_by_nodes(project)
        ctx['data_chart_case_distribution_by_nodes'] = self.get_data_chart_case_distribution_by_nodes(project)
        data_chart_concepts_by_case, data_chart_concepts_by_file = self.get_data_chart_concepts_by_case(project)
        ctx['data_chart_concepts_by_case'] = data_chart_concepts_by_case
        ctx['data_chart_concepts_by_file'] = data_chart_concepts_by_file

        if project.has_codeset:
            ctx['codes'] = project.codeset.codes.order_by('codesystem_name')
        else:
            ctx['codes'] = []

        ctx['logs'] = Log.objects.filter(
            Q(context__project__identifier=project.identifier) | Q(
                object__project__identifier=project.identifier)).order_by('-date_created')
        # demo mode foer stroebl
        # ctx['cases_total'] = 1000  # project.cases.count()
        # ctx['files_total'] = 2548  # project.files.count()
        # ctx[
        #     'annotation_total'] = 489  # project.files.filter(extra_data__application_identifier=settings.ANNOTATION_BACKEND_APPLICATION_IDENTIFIER).count()
        # ctx['challenges_total'] = 1  # project.challenges.count()
        # ctx['challenge_submissions_total'] = 0  # TODO
        # ctx['members'] = project.members.all()
        #
        # ctx['data_chart_file_distribution_by_nodes'] = {'GÖ 1': 1732, 'GÖ 2': 816, 'HD': 0}
        # ctx['data_chart_case_distribution_by_nodes'] = {'GÖ 1': 600, 'GÖ 2': 400, 'HD': 0}
        #
        # ctx['data_chart_concepts_by_case'] = {'HE': 995, 'Keratin': 5, 'Colon': 1000, 'AdenoCA': 1000}
        # ctx['data_chart_concepts_by_file'] = {'HE': 2532, 'Keratin': 16, 'Colon': 2548, 'AdenoCA': 2548}

        # ctx['codes'] = [{
        #     'code': 'Keratin',
        #     'codesystem_name': 'Staining',
        #     'no_cases': 5,
        #     'no_files': 16,
        #     'no_annotations': 0
        # },
        #     {
        #         'code': 'HE',
        #         'codesystem_name': 'Staining',
        #         'no_cases': 995,
        #         'no_files': 2532,
        #         'no_annotations': 0
        #     },
        #     {
        #         'code': 'Colon',
        #         'codesystem_name': 'Organ',
        #         'no_cases': 1000,
        #         'no_files': 2548,
        #         'no_annotations': 0
        #     },
        #     {
        #         'code': 'AdenoCA',
        #         'codesystem_name': 'Tumor',
        #         'no_cases': 1000,
        #         'no_files': 2548,
        #         'no_annotations': 489
        #     },
        # ]
        # ctx['members'] = [{
        #     'human_readable': 'GOE 1',
        #     'no_cases': 600,
        #     'no_files': 1732,
        #     'no_downloaded': 1732
        # },
        #     {
        #         'human_readable': 'GOE 2',
        #         'no_cases': 400,
        #         'no_files': 816,
        #         'no_downloaded': 816
        #     },
        #     {
        #         'human_readable': 'HD',
        #         'no_cases': 0,
        #         'no_files': 0,
        #         'no_downloaded': 0
        #     }
        # ]

        return ctx

    def get_data_chart_file_distribution_by_nodes(self, project):
        # TODO replace by a single query
        d = {}
        for m in project.members.all():
            d[m.user.human_readable] = project.files.filter(origin=m.user).count()
        return d

    def get_data_chart_case_distribution_by_nodes(self, project):
        # TODO replace by a single query
        d = {}
        for m in project.members.all():
            d[m.user.human_readable] = project.cases.filter(origin=m.user).count()
        return d

    def get_data_chart_concepts_by_case(self, project):
        c = {}
        f = {}
        if not project.has_codeset:
            return c, f
        # code.file_codes.filter(projects=project).values_list('case_id', flat=True).distinct().count()
        for co in project.codeset.codes.all():
            c[co.code] = co.file_codes.filter(projects=project).values_list('case_id', flat=True).distinct().count()
            f[co.code] = co.file_codes.filter(projects=project).distinct().count()
        # for m in project.members.all():
        #     d[m.node.human_readable] = project.cases.filter(origin=m.node).count()
        # return d
        return c, f


class CreateProjectView(LoginRequiredMixin, FormView):
    form_class = CreateProjectForm
    template_name = 'project/create.html'

    def get_success_url(self) -> str:
        return reverse('project:detail', kwargs=dict(pk=self.object.pk))

    def form_valid(self, form):
        profile = self.request.user.profile
        data = form.cleaned_data

        form_data = dict(created_by=profile)

        biomarkers_ids = data['biomarkers_ids'].values_list('pk', flat=True)
        if biomarkers_ids.count() > 0:
            form_data['biomarkers'] = Code.objects.filter(pk__in=biomarkers_ids)

        tissue_ids = data['tissue_ids'].values_list('pk', flat=True)
        if tissue_ids.count() > 0:
            form_data['tissue'] = Code.objects.filter(pk__in=tissue_ids)

        disease_ids = data['disease_ids'].values_list('pk', flat=True)
        if disease_ids.count() > 0:
            form_data['disease'] = Code.objects.filter(pk__in=disease_ids)

        self.object = form.save(**form_data)
        self.object.biomarkers.set(form_data['biomarkers'])
        self.object.tissue.set(form_data['tissue'])
        self.object.disease.set(form_data['disease'])

        self.object.add_member(profile)
        self.object.broadcast_create_message()
        return super().form_valid(form)


class PartSubmissionListView(LoginRequiredMixin, ProjectContextMixin, TemplateView):
    template_name = 'project/part-submission-list.html'

    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        project = ctx['project']
        ctx['submissions'] = Submission.objects.filter(
            pk__in=project.challenges.values_list('submissions__pk', flat=True), reference__isnull=False).order_by(
            '-date_created').prefetch_related('submitter', 'challenge')
        return ctx


class SetGroundTruthOfMyData(LoginRequiredMixin, ProjectContextMixin, TemplateView):
    template_name = 'project/set-ground-truth-of-my-data.html'

    def get(self, request, *args, **kwargs):
        project = super().get_project()
        if project.latest_ground_truth_schema is None:
            messages.info(request, 'Create the ground truth schema first before setting your data\'s ground truth.')
            return redirect('project:ground_truth:ground-truth-schema', pk=project.pk)
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        project = super().get_project()
        ctx['csv_schema'] = project.latest_ground_truth_schema
        files_qs = project.cases.filter(origin=self.request.user.profile)
        ctx['cases'] = files_qs[:10]
        ctx['cases_total'] = files_qs.count()
        ctx['files_total'] = project.files_for_user(self.request.user.profile).count() #.filter(origin=self.request.user.profile).count()
        ctx['files_total_with_origin_current_user'] = project.files.filter(origin=self.request.user.profile).distinct('name').count() #.filter(origin=self.request.user.profile).count()

        gt = project.latest_ground_truth_schema.ground_truths.filter(created_by=self.request.user.profile).first()
        ctx['gt_exists'] = gt is not None
        ctx['ground_truth'] = gt
        ctx['encrypted'] = ctx['gt_exists']
        return ctx


class SetGroundTruthOfMyDataAction(LoginRequiredMixin, ProjectContextMixin, View):

    def post(self, request, pk, **kwargs):
        project = self.get_project()

        qs = project.latest_ground_truth_schema.ground_truths.filter(created_by=self.request.user.profile)
        gt_exists = qs.first() is not None
        if gt_exists:
            gt = qs.first()
        else:
            gt = GroundTruth.objects.create(created_by=request.user.profile, schema=project.latest_ground_truth_schema)

        gt.content = request.POST.get('ground_truth')
        gt.save()

        messages.success(request, 'Ground Truth saved.')

        return redirect('project:my_data_ground_truth', pk=project.pk)


class ExportAsCSVView(LoginRequiredMixin, ProjectContextMixin, View):

    def post(self, request, **kwargs):
        dst = f'{slugify(self.get_project().name)}-{timezone.now().isoformat()}.csv'

        # https://docs.djangoproject.com/en/5.0/howto/outputting-csv/
        class Echo:
            def write(self, value):
                return value

        def get_rows():
            files = self.get_project().files_for_user(self.request.user.profile)
            for f in files:
                yield [f.id_as_str, f.identifier, f.case.name, f.name, f.path, f.original_path, f.original_filename,
                       f.origin.identifier, f.imported]

        FIELDS = ['id', 'identifier', 'case', 'name', 'path', 'original_path', 'original_filename', 'origin',
                  'imported']

        writer = csv.writer(Echo())
        return StreamingHttpResponse(
            (writer.writerow(row) for row in
             itertools.chain([FIELDS], get_rows())),
            content_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="{dst}"'},
        )


class CreateWebsiteView(LoginRequiredMixin, ProjectContextMixin, TemplateView):
    template_name = 'project/website/create.html'

class CreateWebsitePreviewView(LoginRequiredMixin, ProjectContextMixin, TemplateView):
    template_name = 'project/website/preview.html'


    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        ctx = super().get_context_data(**kwargs)




        return ctx
