import json
import logging
from datetime import timedelta

from annoying.fields import AutoOneToOneField
from django.db import models
from django.urls import reverse
from django.utils import timezone

from apps.blockchain.messages import Identifiable
from apps.challenge.challenge_submission.managers import SubmissionManager
from apps.challenge.challenge_targetmetric.models import TargetMetric
from apps.challenge.models import Challenge
from apps.computing.computing_artifact.models import ComputingJobArtifact
from apps.computing.computing_executions.models import ComputingJobExecution
from apps.computing.computing_log.models import ComputingJobLogEntry
from apps.computing.models import ComputingJobDefinition, ComputingJobTemplate, ComputingPipeline
from apps.core import identifier
from apps.core.models import Base, CreatedByMixin, IdentifieableMixin, OriginMixin
from apps.federation.file_transfer.models import TransferJob
from apps.federation.messages import Message
from apps.project.tasks import create_transfer_job_and_start, create_transfer_items_for_files_and_start
from apps.share.share_token.models import ShareToken
from apps.storage.models import File
from apps.user.user_profile.models import Profile


class Submission(CreatedByMixin, OriginMixin, IdentifieableMixin, Base):
    objects = SubmissionManager()
    '''
    Submission for validation results (not training).
    '''
    challenge = models.ForeignKey(Challenge, on_delete=models.CASCADE, related_name='submissions')
    computing_pipeline = models.OneToOneField(ComputingPipeline, on_delete=models.CASCADE,
                                              related_name='submission', null=True, blank=True)
    name = models.CharField(max_length=100)
    # on the challenge organizer node this is the real submitter
    submitter = models.ForeignKey('user_profile.Profile', on_delete=models.CASCADE, null=True,
                                  related_name='submissions')

    fields = models.JSONField(default=dict, blank=True, null=True)
    target_metric_value = models.ManyToManyField(TargetMetric, through='TargetMetricValue')

    computing_job_executions = models.ManyToManyField('computing_executions.ComputingJobExecution',
                                                      related_name='submissions', blank=True)

    # this ought to be the identifier of the original submission if and only if the submission was forwarded to other nodes
    # it is null on the submitter node
    reference = models.CharField(max_length=500, null=True, blank=True)
    nodes = models.ManyToManyField('user_profile.Profile', through='challenge_submission.SubmissionToNodes', blank=True)

    # TODO password for docker registry

    def get_absolute_url(self):
        return reverse('challenge:challenge_submission:detail',
                       kwargs=dict(pk=self.challenge_id, submission_pk=self.pk))

    @property
    def is_part_submission(self):
        return self.reference is not None

    @property
    def status_ordered(self):
        return self.status.order_by('-date_created').all()

    def __str__(self):
        return self.name

    def to_identifiable(self):
        return Identifiable(model="submission", display=self.name, identifier=self.identifier)

    def extract_target_metrics(self, job_execution: ComputingJobExecution):
        for metric in self.challenge.target_metrics.all():
            artefact = job_execution.artifacts.filter(file__name=metric.filename).first()
            if artefact is None:
                # TODO how to notify the user here? maybe set execution to state fail
                logging.error('Result artefact %s not found in run %s for target metric %s.', metric.filename,
                              job_execution.pk)
                continue

            value = 'Not found.'
            with artefact.file.as_path.open() as f:
                o = json.load(f)
                if metric.key in o:
                    value = o[metric.key]

            metric_value = TargetMetricValue.objects.filter(submission=self, target_metric=metric).first()
            # update metric value or create new one.
            if metric_value is None:
                TargetMetricValue.objects.create(submission=self,
                                                 target_metric=metric,
                                                 value=value)
            else:
                metric_value.value = value
                metric_value.save()

    def distribute_to_nodes(self):
        from apps.share.api import ShareBuilder
        from apps.share.tasks import send_share_to_sharetokens

        if self.is_part_submission:
            logging.error('This submission is a part of a submission and cannot be distributed.')
            return

        # TODO what are created_by and origin here?? is it the current user
        # TODO or the submitter
        # TODO the submitter may or may not be connected to the data owner

        data_files = {s.identifier: s.data_file for s in self.challenge.pipeline.stages.all() if
                      s.data_file is not None}
        # TODO for submission part result, serialize the full computing pipeline and not just the templates

        # resend submission to destinations and do not create share again.
        destinations = self.challenge.data_origins
        qs = SubmissionToNodes.objects.filter(submission=self)
        for sn in qs:
            sn.share_token.send_to_node()
            destinations = destinations.exclude(pk=sn.node_id)

        if not destinations.exists():
            logging.warning("No destinations left. Aborting.")
            return

        ev_codes = self.challenge.evaluationcode_set.all()

        builder = ShareBuilder(name='Submission',
                               challenge=self.challenge,
                               created_by=self.created_by,
                               origin=self.origin,
                               type="submission-part",
                               pk=None)
        share = builder.add_challenge_handler(dict(challenge=self.challenge),
                                              handler_init_kwargs={'computing_pipeline': 'full'}) \
            .add_submission_handler({'submission': self, 'data_files': data_files}) \
            .add_evaluation_code_handler(ev_codes) \
            .build()

        valid_from = timezone.now()
        valid_until = valid_from + timedelta(days=365)

        # TODO if current node has also data then add the submission and stuff to this submissiontonodes
        # the submission already has the computing pipeline created.

        for p in destinations:
            st = ShareToken.objects.create(created_by=self.challenge.created_by,
                                           share=share,
                                           identifier=identifier.create_random('share_token'),
                                           recipient=p,
                                           valid_from=valid_from,
                                           valid_until=valid_until)
            SubmissionToNodes.objects.create(submission=self, node=p, share_token=st,
                                             status=SubmissionToNodes.Status.SENT)

        logging.info('Done creating part submission.')
        send_share_to_sharetokens(share.pk)

    @staticmethod
    def import_submission(**kwargs):
        message: Message = kwargs.get('message')
        origin = Profile.objects.get_by_identifier(message.object.sender)
        recipient = Profile.objects.get_by_identifier(message.object.recipient)

        if message.type == 'create':
            Submission.create_submission_from_message(message, origin, recipient)
        if message.type == 'update':
            Submission.update_submission(message, origin, recipient)

    @staticmethod
    def create_submission_from_message(message: Message, origin: Profile, recipient: Profile):
        content = message.object.content
        submission = content['submission']
        Submission.create_submission(submission, origin)

    @staticmethod
    def create_submission(submission, origin: Profile, part_submission=False):
        challenge = Challenge.objects.get_by_identifier(submission['challenge'])
        submitter = Profile.get_or_create_remote_user(submission['submitter']['identifier'],
                                                      submission['submitter']['human_readable'],
                                                      identity=None,
                                                      eth_address=None)  # the user will always be already imported here because it was published before it could participate in any federated actions.
        kw = {}
        qs_kw = {}
        if part_submission:
            kw['reference'] = submission['identifier']
            kw['identifier'] = identifier.create_random('submission')
            qs_kw['reference'] = kw['reference']
        else:
            kw['identifier'] = submission['identifier']
            qs_kw['identifier'] = kw['identifier']

        # if on a single node a submission may exist multiple times: one created by the submitter, and one 'received' by the challenge organizer
        # qs = Submission.objects.filter(**qs_kw)
        # if qs.exists():
        #     logging.warning(f"Submission with identifier = [{kw['identifier']}] or reference = [{kw['reference']}] already exists.")
        #     return

        s = Submission.objects.create(name=submission.get('name', ''),
                                      created_by=origin,
                                      challenge=challenge,
                                      submitter=submitter,
                                      origin=origin,
                                      fields=submission.get('fields', None),
                                      **kw)
        pipeline = ComputingPipeline.from_template(challenge.pipeline, origin, challenge, s)
        s.computing_pipeline = pipeline
        s.save()
        if pipeline is None:
            raise ValueError('Pipeline is None.')

        template = ComputingJobTemplate.objects.get_by_identifier(s.fields['template_identifier'])
        # create the templated job definition
        ComputingJobDefinition.create_from_template(template, pipeline, s.fields)
        # create k8s spec for computing job in a challenge
        s.save(update_fields=['computing_pipeline'])

        # already create the submission to nodes models
        for p in challenge.data_origins:
            SubmissionToNodes.objects.create(submission=s, node=p, status=SubmissionToNodes.Status.PENDING)

    @staticmethod
    def update_submission(message: Message, origin: Profile, recipient: Profile):
        content = message.object.content
        updated_fields = content['updated_fields']
        identifier = content['identifier']
        # TODO submitter=recipient is correct?
        submission = Submission.objects.get(identifier=identifier, origin=recipient, submitter=recipient)
        for field in updated_fields:
            val = content[field]
            if field == 'status':
                SubmissionStatus.objects.get_or_create(submission=submission,
                                                       status=SubmissionStatus.Status[val.upper()],
                                                       message=content.get('message', None)
                                                       )
        submission.save()

    # @staticmethod
    # def import_submission_result_part(message, submission, sender, results, reference, **kwargs):
    #     logging.info('[start] import submission results part.')
    #
    #     logging.info('[end] import submission results part.')

    @staticmethod
    def import_submission_result(**kwargs):
        logging.info('[start] import submission results.')

        message: Message = kwargs.get('message')
        # recipient = Profile.objects.get_by_identifier(identifier.from_string(message.to))
        object = message.object
        sender = Profile.objects.get_by_identifier(object.sender)
        recipient = Profile.objects.get_by_identifier(object.recipient)
        created_by = sender
        reference = object.content.get('reference')

        if reference is not None:
            # submission = Submission.objects.get_by_identifier(reference, origin=recipient) # if the submission was created on the same node as well this may pose a problem.
            submission = Submission.objects.get_by_identifier(reference) # TODO add the origin or so here? if the submission was created on another node that should work fine as it is but if it was created on the same node not sure  # if the submission was created on the same node as well this may pose a problem.
        else:
            submission = Submission.objects.get_by_identifier(object.content.get('submission'), origin__isnull=True)
        result_list = object.content.get('content')
        if not isinstance(result_list, list):
            result_list = [result_list]

        for results in result_list:
            # if reference is not None:
            #     return Submission.import_submission_result_part(message, submission, sender, results, reference)
            # make a list so generator fires
            logging.info('[start] import files')
            files = results.get('files', '')
            File.import_file(files=files, created_by=recipient)
            logging.info('[end] import files')

            logging.info('[start] import ComputingJobDefinition')
            ComputingJobDefinition.import_definition(definitions=results.get('computing_job_definitions', ''),
                                                     origin=sender,
                                                     created_by=created_by,
                                                     submission=submission,
                                                     submission_reference=reference)
            logging.info('[end] import ComputingJobDefinition')
            logging.info('[start] import ComputingJobExecution')
            ecs = ComputingJobExecution.import_execution(executions=results.get('computing_job_executions', ''),
                                                         origin=sender,
                                                         created_by=created_by,
                                                         submission=submission)
            logging.info('[end] import ComputingJobExecution')

            logging.info('[start] import ComputingJobLogEntry')
            ComputingJobLogEntry.import_log(logs=results.get('logs', ''), created_by=created_by, submission_id=submission.pk)
            logging.info('[end] import ComputingJobLogEntry')

            logging.info('[start] import ComputingJobArtifact')
            artefact_ids = ComputingJobArtifact.import_artefact(artefacts=results.get('artefacts', ''),
                                                                created_by=created_by,
                                                                submission_id=submission.pk)
            logging.info('[end] import ComputingJobArtifact')

            logging.info('Set submission status to RESULTS_RECEIVED')
            status = SubmissionStatus.objects.create(submission=submission,
                                                     status=SubmissionStatus.Status.RESULTS_RECEIVED)
            status.executions.set(ComputingJobExecution.objects.filter(pk__in=ecs))

            # create artefacts as transferitem so they will be downloaded
            if artefact_ids is not None:
                file_ids = [str(a.file_id) for a in ComputingJobArtifact.objects.filter(pk__in=artefact_ids)]
                if len(file_ids) > 0:
                    logging.info('Create TransferItems to download artefacts.')
                    download_query = {'id__in': file_ids}
                    tj = TransferJob.objects.create(project=submission.challenge.project,
                                                    created_by=Profile.objects.get_by_identifier(object.recipient),
                                                    query=download_query)
                    # create_transfer_job_and_start.delay(tj.id_as_str, download_query, False)
                    # bypass the task create_transfer_job_and_start
                    create_transfer_items_for_files_and_start(
                        transfer_job=tj,
                        files=File.objects.filter(**download_query)
                    )
        if reference is not None:
            SubmissionToNodes.objects.filter(node=sender, submission=submission).update(
                status=SubmissionToNodes.Status.RESULTS)

        logging.info('[end] import submission results.')


class SubmissionToNodes(Base):
    """
    This model is used if a submission needs to be forwarded to another node for evaluation there.
    """

    class Status(models.TextChoices):
        PENDING = 'pending'
        SENT = 'sent'
        ERROR = 'error'
        SENDING = 'sending'
        RESULTS = 'results'

    status = models.CharField(max_length=7, choices=Status.choices, default=Status.PENDING)
    submission = models.ForeignKey(Submission, on_delete=models.CASCADE)
    node = models.ForeignKey(Profile, on_delete=models.CASCADE)
    share_token = models.ForeignKey('share_token.ShareToken', on_delete=models.CASCADE, null=True, blank=True)

    @property
    def has_results(self):
        return self.status == SubmissionToNodes.Status.RESULTS

    @property
    def has_error(self):
        return self.status == SubmissionToNodes.Status.ERROR

    @property
    def is_pending(self):
        return self.status == SubmissionToNodes.Status.PENDING

    @property
    def is_sent(self):
        return self.status == SubmissionToNodes.Status.SENT


class TargetMetricValue(Base):
    target_metric = models.ForeignKey('challenge_targetmetric.TargetMetric', on_delete=models.CASCADE)
    submission = models.ForeignKey(Submission, on_delete=models.CASCADE)
    value = models.TextField()

    def __str__(self):
        return f'{self.target_metric.key} = {self.value}'

    @staticmethod
    def import_list(objects: list, submission):
        arr = []
        for m in objects:
            key = m.get('key')
            value = m.get('value')
            target_metric = TargetMetric.objects.get(key=key,
                                                     challenge=submission.challenge)

            tmv, _ = TargetMetricValue.objects.get_or_create(target_metric=target_metric,
                                                             submission=submission)
            tmv.value = value
            tmv.save()
            arr.append(tmv)
        return arr


class SubmissionStatus(Base):
    class Status(models.TextChoices):
        PENDING = 'pending'
        SENT = 'sent'
        EXECUTED = 'executed'
        RESULTS_RECEIVED = 'results_received'
        REJECTED = 'rejected'
        RANKED = 'ranked'
        ERROR = 'error'

    submission = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name='status')
    status = models.CharField(max_length=30, default=Status.PENDING, choices=Status.choices)
    message = models.TextField(blank=True, null=True)  # any additional message by challenge organizer
    executions = models.ManyToManyField('computing_executions.ComputingJobExecution')

    @property
    def icon(self):
        if self.is_pending:
            return 'ti-hourglass-empty'
        if self.is_sent:
            return 'ti-send'
        if self.is_executed:
            return 'ti-run'
        if self.is_results_received:
            return 'ti-mailbox'
        if self.is_rejected:
            return 'ti-ban'
        if self.is_ranked:
            return 'ti-military-rank'
        if self.is_error:
            return 'ti-exclamation-circle'

        return 'ti-question-mark'

    @property
    def is_error(self):
        return self.status == SubmissionStatus.Status.ERROR

    @property
    def is_pending(self):
        return self.status == SubmissionStatus.Status.PENDING

    @property
    def is_executed(self):
        return self.status == SubmissionStatus.Status.EXECUTED

    @property
    def is_results_received(self):
        return self.status == SubmissionStatus.Status.RESULTS_RECEIVED

    @property
    def is_rejected(self):
        return self.status == SubmissionStatus.Status.REJECTED

    @property
    def is_ranked(self):
        return self.status == SubmissionStatus.Status.RANKED

    @property
    def is_sent(self):
        return self.status == SubmissionStatus.Status.SENT

    @property
    def title(self):
        if self.is_pending:
            return 'Pending'
        if self.is_sent:
            return 'Sent'
        if self.is_executed:
            return 'Submission executed'
        if self.is_results_received:
            return 'Results received'
        if self.is_rejected:
            return 'Rejected'
        if self.is_ranked:
            return 'Ranked'

        return 'Unknown'

    @property
    def has_message(self):
        return self.message is not None and len(self.message.strip()) > 0

    def __str__(self):
        return f'{self.status} ({self.submission})'


class SubmissionLogEntry(Base):
    log_entry = AutoOneToOneField('computing_log.ComputingJobLogEntry',
                                  on_delete=models.CASCADE,
                                  related_name='submission_log_entry')
    obscure = models.BooleanField(default=True)
    sent = models.BooleanField(default=False)


class SubmissionArtefact(Base):
    artefact = AutoOneToOneField('computing_artifact.ComputingJobArtifact',
                                 on_delete=models.CASCADE,
                                 related_name='submission_artefact')
    do_not_send = models.BooleanField(default=True)
    sent = models.BooleanField(default=False)

# @receiver(post_save, sender='computing_executions.ComputingJobExecution')
# def signal_computing_job_success_calculate_target_metric(sender, instance, created, **kwargs):
#     # if instance is completed,
#     if created: return
