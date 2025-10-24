import logging
from functools import partial
from typing import Any

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, AccessMixin
from django.db import transaction
from django.db.models import Q, Sum
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse_lazy, reverse
from django.utils import timezone
from django.utils.text import slugify
from django.views import View
from django.views.generic import TemplateView, FormView
from keycloak import KeycloakAuthenticationError

from apps.challenge.challenge_client import forms, tasks
from apps.challenge.challenge_client.forms import ProfileForm
from apps.challenge.challenge_client.models import ChallengeParticipantApproval
from apps.challenge.challenge_client.tasks import create_transfer_job_and_start_for_challenge_client
from apps.challenge.challenge_leaderboard.models import LeaderboardEntry
from apps.challenge.challenge_submission.models import Submission, SubmissionStatus
from apps.challenge.models import Challenge
from apps.computing.computing_artifact.models import ComputingJobArtifact
from apps.computing.computing_log.models import ComputingJobLogEntry
from apps.computing.models import ComputingJobDefinition
from apps.core import identifier
from apps.federation.file_transfer.models import TransferJob, DownloadToken
from apps.permission.models import Permission
from apps.storage.storage_exporter.models import ExportJob
from apps.storage.storage_exporter.tasks import export_from_job
from apps.user.user_profile.models import Profile
from apps.utils import create_user_on_keycloak, get_node_origin, get_keycloak_admin


class ChallengeApprovedMixin(AccessMixin):

    def get_challenge(self):
        # Retrieve the challenge instance using pk or another unique identifier
        return get_object_or_404(Challenge, pk=self.kwargs.get('pk'))

    def dispatch(self, request, *args, **kwargs):
        # Ensure the user is logged in
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        # Get the challenge instance from the URL
        challenge = self.get_challenge()

        # Check if the user is approved for this challenge
        approval = ChallengeParticipantApproval.objects.filter(
            challenge_participants__challenge=challenge,
            profile=request.user.profile
        ).first()

        # If no approval or not approved, raise a permission error
        if not approval or not approval.approved:
            return redirect('challenge_client:challenge-not-enrolled', pk=challenge.pk)

        return super().dispatch(request, *args, **kwargs)


class ChallengeListView(TemplateView):
    template_name = 'challenge/challenge_client/index.html'

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        ctx.update({
            'challenges': Challenge.objects.all()
        })
        return ctx


class EnrollInChallengeView(LoginRequiredMixin, TemplateView):
    template_name = 'challenge/challenge_client/enroll.html'

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        challenge = get_object_or_404(Challenge, pk=self.kwargs.get('pk'))

        ctx.update({'challenge': challenge})
        return ctx

    def get(self, request, pk, **kwargs):
        challenge = get_object_or_404(Challenge, pk=pk)

        # ✅ Check if the user has an explicit approval
        approval = ChallengeParticipantApproval.objects.filter(
            challenge_participants__challenge=challenge, profile=request.user.profile
        ).first()

        if not approval:
            messages.error(request, "You need to be explicitly approved to participate in this challenge.")
            return super().get(request, pk, **kwargs)
            # return redirect('challenge_client:challenge-detail', pk=challenge.pk)

        if not approval.approved:
            messages.warning(request, "Your enrollment is still pending approval.")
            return super().get(request, pk, **kwargs)
            # return redirect('challenge_client:challenge-detail', pk=challenge.pk)

        # ✅ Check if user is already enrolled
        if challenge.participants.profiles.filter(pk=request.user.profile.pk).exists():
            messages.info(request, "You are already enrolled in this challenge.")
            return redirect('challenge_client:challenge-detail', pk=challenge.pk)

        return super().get(request, pk, **kwargs)


    def post(self, request, pk, **kwargs):
        challenge = get_object_or_404(Challenge, pk=pk)

        # ✅ Ensure the user has explicit approval
        approval, created = ChallengeParticipantApproval.objects.get_or_create(
            challenge_participants=challenge.participants, profile=request.user.profile
        )

        if not approval.approved:
            messages.error(request, "You cannot access the challenge until you have been approved.")
            return redirect('challenge_client:challenge-detail', pk=pk)

        # ✅ Enroll the user since they are approved
        challenge.participants.profiles.add(request.user.profile)
        messages.success(request, f'You have successfully enrolled in {challenge.name}.')
        return redirect('challenge_client:challenge-detail', pk=pk)

class ChallengeAsContextDataMixin:

    def get_challenge(self):
        return Challenge.objects.get(pk=self.get_challenge_id())

    def get_challenge_id(self):
        return self.kwargs.get('pk', None)

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        ctx.update({
            'challenge': self.get_challenge()
        })
        return ctx

class NotEnrolledTemplateView(LoginRequiredMixin, ChallengeAsContextDataMixin, TemplateView):
    template_name = 'challenge/challenge_client/not_enrolled.html'


class ChallengeDetailView(ChallengeAsContextDataMixin, TemplateView):
    template_name = 'challenge/challenge_client/detail.html'


class ChallengeDatasetsView(ChallengeAsContextDataMixin, TemplateView):
    template_name = 'challenge/challenge_client/datasets.html'

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        challenge = ctx['challenge']
        ctx.update({
            'datasets': challenge.datasets.all()
        })
        return ctx


class ChallengeDatasetsOverviewView(ChallengeAsContextDataMixin, TemplateView):
    template_name = 'challenge/challenge_client/dataset/overview.html'

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        challenge = ctx['challenge']
        ctx.update({
            'challenge': challenge,
            'datasets': challenge.datasets.all()
        })
        return ctx


class DatasetMixin(ChallengeAsContextDataMixin):

    def get_dataset_id(self):
        return self.kwargs.get('dataset_pk', None)

    def get_dataset(self):
        return self.get_challenge().datasets.get(pk=self.get_dataset_id())

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        ds = self.get_challenge().datasets.get(pk=self.kwargs.get('dataset_pk', None))
        ctx.update({
            'dataset': ds,
            'number_of_cases': ds.files.values_list('case_id', flat=True).distinct().count(),
        })
        return ctx


class ChallengeDatasetsDetailView(DatasetMixin, TemplateView):
    template_name = 'challenge/challenge_client/dataset/detail.html'


class ChallengeDatasetsDetailActionView(LoginRequiredMixin, ChallengeApprovedMixin, DatasetMixin, View):

    def post(self, request, **kwargs):
        data = request.POST

        if 'button_download' in data:
            query = {'pk__in': []}
            for f in self.get_dataset().files.exclude(imported=True):
                query['pk__in'].append(f.id_as_str)

            tj = TransferJob.objects.create(query=query, created_by=request.user.profile)
            transaction.on_commit(partial(create_transfer_job_and_start_for_challenge_client.delay, tj.id_as_str))
            messages.success(request, 'Dataset will be downloaded.')

        if 'button_export' in data:
            job = ExportJob.objects.create(
                created_by=request.user.profile,
                export_folder=f'{slugify(self.get_challenge().name)}-{slugify(self.get_dataset().name)}-{timezone.now()}',
                challenge=self.get_challenge(),
            )
            job.files.set(self.get_dataset().files.filter(imported=True))
            files_all = job.files.all()
            # TODO create in celery task

            # download token for download in url and NOT in centauron
            for f in files_all:
                DownloadToken.objects.create(file=f,
                                             created_by=request.user.profile,
                                             for_user=request.user.profile,
                                             challenge=self.get_challenge())
            Permission.objects.create_permissions(permission=Permission.Permission.ALLOW,
                                                  actions=[Permission.Action.DOWNLOAD],
                                                  created_by=request.user.profile,
                                                  users=[request.user.profile],
                                                  queryset=files_all)
            return redirect('challenge_client:challenge-datasets-exports-detail', pk=kwargs.get('pk'), job_pk=job.pk)
        return redirect('challenge_client:challenge-datasets-detail', pk=kwargs.get('pk'),
                        dataset_pk=kwargs.get('dataset_pk'))


class ExportDetailView(LoginRequiredMixin, ChallengeAsContextDataMixin, TemplateView):
    template_name = 'challenge/challenge_client/dataset/export.html'

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        # TODO add challenge here
        job = ExportJob.objects.get(created_by=self.request.user.profile, pk=self.kwargs['job_pk'])
        ctx['job'] = job
        ctx['urls'] = [f.build_url() for f in
                       DownloadToken.objects.filter(for_user=self.request.user.profile, file__in=job.files.all())]
        ctx['total_size'] = job.files.aggregate(Sum("size"))['size__sum']
        return ctx


class ExportDetailActionsView(LoginRequiredMixin, ChallengeAsContextDataMixin, View):

    def post(self, request, **kwargs):
        data = request.POST
        job = ExportJob.objects.get(created_by=self.request.user.profile, pk=self.kwargs['job_pk'])
        if 'btn_start' in data:
            transaction.on_commit(lambda: export_from_job.delay(job.id_as_str))
            messages.success(request, f'Files will be exported into {job.export_folder} in background.')
        return redirect('challenge_client:challenge-datasets-exports-detail', pk=kwargs.get('pk'), job_pk=job.pk)


class ExportListView(LoginRequiredMixin, ChallengeAsContextDataMixin, TemplateView):
    template_name = 'challenge/challenge_client/dataset/export_list.html'

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        ctx['jobs'] = ExportJob.objects.filter(created_by=self.request.user.profile,
                                               challenge_id=self.get_challenge_id())
        return ctx


class ChallengeSubmissionsListView(LoginRequiredMixin,ChallengeApprovedMixin, ChallengeAsContextDataMixin, TemplateView):
    template_name = 'challenge/challenge_client/submission/list.html'

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        challenge = ctx['challenge']
        ctx.update({
            'challenge': challenge,
            'submissions': challenge.submissions.filter(origin__isnull=True).order_by('-date_created'),
            'submissions_enabled': challenge.pipeline is not None
        })
        return ctx


class ChallengeSubmissionCreateView(LoginRequiredMixin, ChallengeAsContextDataMixin, FormView):
    template_name = 'challenge/challenge_client/submission/create.html'
    form_class = forms.SubmissionCreateForm

    def get_form_kwargs(self) -> dict[str, Any]:
        s = super().get_form_kwargs()
        challenge = Challenge.objects.get(pk=self.kwargs.get('pk'))
        template = challenge.pipeline.stages.order_by('position').first().template
        d = {}
        if template is not None:
        # fields = list(map(lambda e: f'{template.definition.name}.{e}', template.template_fields)) # preparation for multi-stage tempaltes
            fields = template.template_fields
            d['fields'] = fields
            d['template_identifier'] = template.identifier
        return {**s, **d}

    def get_initial(self) -> dict[str, Any]:
        if settings.DEBUG:
            return {
                # 'script': 'python /cyto_processor_local/code/csv_observer.py --conf /cyto_processor_local/code/processor_config.json --csv /data.csv',
                # 'cat /data.csv && cat /data.csv > /output/res.txt',
                'script': 'cat /data.csv',  # python main.py',
                'image': 'busybox',  # 'docker.cytoslider.com/centauron/testcomputingclient:latest',  # 'busybox:latest',
                'name': 'bb',
                'local': self.request.GET.get('type') == 'local'
            }
        return {}

    def form_valid(self, form):
        data = form.cleaned_data
        # job = ComputingJobDefinition.objects.create(created_by=self.request.user.profile,
        #                                             docker_image=data['image'],
        #                                             entrypoint=[data['script']],
        #                                             identifier=Identifier.objects.create_random('computing-job-execution'),
        #                                             type=ComputingJobDefinition.Type.VALIDATION)
        # TODO until now only a single template is supported. extend to support templates for multiple job definitions.

        fields = {
            'identifier': identifier.create_random('computing-job-execution'),
            'type': ComputingJobDefinition.Type.VALIDATION,
            'template_identifier': str(form.template_identifier),
            'template': {}
        }
        for k, v in data.items():
            fields['template'][k] = v

        submission = Submission.objects.create(challenge=Challenge.objects.get(pk=self.kwargs.get('pk', None)),
                                               created_by=self.request.user.profile,
                                               submitter=self.request.user.profile,
                                               identifier=identifier.create_random('submission'),
                                               name=data['name'],
                                               fields=fields)
        SubmissionStatus.objects.create(submission=submission)
        messages.success(self.request, 'Submission sent successfully.')

        transaction.on_commit(partial(tasks.send_submission_to_challenge_origin.delay, submission.id_as_str))
        return redirect('challenge_client:challenge-submission-detail', pk=self.kwargs.get('pk'),
                        submission_pk=submission.pk)


class ChallengeSubmissionsDetailView(LoginRequiredMixin, ChallengeApprovedMixin, ChallengeAsContextDataMixin, TemplateView):
    template_name = 'challenge/challenge_client/submission/detail.html'

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        challenge = ctx['challenge']
        ctx.update({
            'submission': challenge.submissions.get(pk=self.kwargs.get('submission_pk', None))
        })
        return ctx


class ChallengeResultDetailView(LoginRequiredMixin, ChallengeApprovedMixin, ChallengeAsContextDataMixin, TemplateView):
    template_name = 'challenge/challenge_client/submission/result/detail.html'

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        challenge = ctx['challenge']

        submission = challenge.submissions.get(pk=self.kwargs.get('submission_pk', None))
        status = submission.status.get(pk=self.kwargs.get('status_pk'))
        executions = submission.computing_job_executions.order_by('definition__position')
        definitions_id = set(executions.values_list('definition', flat=True))
        definitions = ComputingJobDefinition.objects.filter(pk__in=definitions_id).filter(~Q(name='.post')).order_by(
            'position').prefetch_related('executions', 'executions__log_entries')
        # cl = ComputingJobLogEntry.objects.filter(
        #     computing_job__identifier='fhir.ak.dev.centauron.net#computing-job-execution::a99e3234-c433-4ee7-ae2c-d5a6ef5c3321')
        ctx.update({
            'definitions': definitions,
            'submission': submission,
            'status': status,
            'executions': executions
        })
        return ctx


class ChallengeLeaderboardView(LoginRequiredMixin,  ChallengeApprovedMixin,ChallengeAsContextDataMixin, TemplateView):
    template_name = 'challenge/challenge_client/leaderboard.html'

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        challenge = ctx['challenge']
        entries = LeaderboardEntry.objects.filter(challenge=challenge).order_by('position')
        target_metrics = challenge.target_metrics.all()
        sort_criterion = challenge.target_metrics.filter(sort__isnull=False)
        last_modified = entries.order_by('last_modified').first().last_modified if entries.count() > 0 else None

        ctx.update({
            'target_metrics': target_metrics,
            'sort_criterion': sort_criterion,
            'entries': entries,
            'last_modified': last_modified,
        })
        return ctx


class LogView(LoginRequiredMixin, ChallengeApprovedMixin, ChallengeAsContextDataMixin, TemplateView):
    template_name = 'challenge/challenge_client/partial/log.html'

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        id = self.request.GET.get('id')
        cls = ComputingJobLogEntry.objects.filter(computing_job_id=id,
                                                  computing_job__definition__submission__computing_pipeline__isnull=True).order_by(
            'position')
        ctx.update({
            'log_entries': cls
        })
        return ctx


class ArtefactView(LoginRequiredMixin,  ChallengeApprovedMixin,ChallengeAsContextDataMixin, TemplateView):
    template_name = 'challenge/challenge_client/partial/artefact.html'

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        challenge = ctx['challenge']
        # TODO add challenge to query
        id = self.request.GET.get('id')
        cls = ComputingJobArtifact.objects.filter(computing_job_id=id,
                                                  computing_job__definition__submission__computing_pipeline__isnull=True)
        ctx.update({
            'artefacts': cls,
            'submission': challenge.submissions.get(pk=self.kwargs.get('submission_pk', None))
        })
        return ctx


class DatasetExportView(LoginRequiredMixin,  ChallengeApprovedMixin,ChallengeAsContextDataMixin, TemplateView):
    template_name = 'challenge/challenge_client/dataset/dataset_export.html'


class RegisterSuccessView(TemplateView):
    template_name = 'challenge/challenge_client/register_success.html'


class RegisterView(FormView):
    template_name = "challenge/challenge_client/register.html"
    form_class = ProfileForm
    success_url = reverse_lazy("challenge_client:register_success")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context

    def form_valid(self, form):
        data = form.cleaned_data
        logging.info("Start creating user...")
        userid, did, user_identifier = create_user_on_keycloak(data.get('email'),
                                      False,
                                      email=data.get('email'))
        logging.info("User created.")

        # on the first login, the user is added to this profile
        logging.info('Create user profile')
        profile:Profile = Profile.objects.create(
            identity=did,
            human_readable=data.get('human_readable'),
            organization=data.get('organization'),
            orcid=data.get('orcid'),
            pubmed=data.get('pubmed'),
            google_scholar=data.get('google_scholar'),
            node=get_node_origin(),
            identifier=user_identifier
        )
        logging.info('Create private key.')
        profile.generate_private_key()

        logging.info('User profile created.')
        logging.info('Publishing...')
        # user must be published in order to be able to send submission etc.
        profile.publish_to_registry()
        logging.info('Published successfully.')

        try:
            keycloak_admin = get_keycloak_admin()
        except KeycloakAuthenticationError as e:
            logging.error(e)
            raise e

        logging.info('Send verification email.')
        uri = self.request.build_absolute_uri(reverse('challenge_client:challenge-list'))
        try:
            keycloak_admin.send_verify_email(userid,
                                             client_id=settings.KEYCLOAK_CLIENT_ID,
                                             redirect_uri=uri)
        except Exception as e:
            logging.error(e)
        logging.info('Done.')

        return redirect(self.success_url)
