import logging

from django.db import models, transaction

from apps.challenge.challenge_dataset.models import Dataset, EvaluationCode
from apps.challenge.challenge_targetmetric.models import TargetMetric
from apps.challenge.models import Challenge
from apps.computing.models import ComputingPipeline
from apps.core import identifier
from apps.core.models import Base, IdentifieableMixin, CreatedByMixin, OriginMixin
from apps.event.models import Event
from apps.federation.inbox.models import InboxMessage
from apps.federation.messages import Message, RetractShareMessageContent
from apps.node.models import Node
from apps.project.models import Project
from apps.project.project_case.models import Case
from apps.project.project_ground_truth.models import GroundTruthSchema
from apps.storage.extra_data.models import ExtraData
from apps.storage.models import File
from apps.terminology.models import Code, CodeSystem
from apps.user.user_profile.models import Profile
from apps.utils import get_user_node, get_node_origin


class ShareableMixin:

    def create_share(self, project_identifier, valid_from, valid_until, from_, to, file_query):
        pass


class Share(CreatedByMixin, OriginMixin, IdentifieableMixin, Base):

    # unique constraint does not work anymore if the share is shared with a user on the same node
    # class Meta:
    #     constraints = [
    #         # models.UniqueConstraint(name='unique_share_name_per_project_and_user', fields=['name', 'project', 'created_by'])
    #     ]

    content = models.JSONField(default=dict)
    files = models.ManyToManyField("storage.File", related_name="shares")
    challenges = models.ManyToManyField("challenge.Challenge", related_name="shares")
    codes = models.ManyToManyField('terminology.Code', related_name='shares')
    cases = models.ManyToManyField("project_case.Case", related_name="shares")
    datasets = models.ManyToManyField("challenge_dataset.Dataset", related_name="shares")
    codesystem = models.ManyToManyField('terminology.CodeSystem', related_name='shares')
    computing_job_executions = models.ManyToManyField('computing_executions.ComputingJobExecution',
                                                      related_name='shares')
    computing_job_definitions = models.ManyToManyField('computing.ComputingJobDefinition', related_name='shares')
    computing_job_logs = models.ManyToManyField('computing_log.ComputingJobLogEntry', related_name='shares')
    computing_job_artefacts = models.ManyToManyField('computing_artifact.ComputingJobArtifact', related_name='shares')
    # TODO add other type of resources that can be shared
    submissions = models.ManyToManyField('challenge_submission.Submission', related_name='shares')
    extra_data = models.ManyToManyField('extra_data.ExtraData', related_name='shares')
    evaluation_code = models.ManyToManyField('challenge_dataset.EvaluationCode', related_name='shares')

    name = models.CharField(max_length=500)
    description = models.TextField(null=True, blank=True)
    file_query = models.JSONField(default=dict, blank=True)
    project = models.ForeignKey('project.Project', related_name='shares', on_delete=models.CASCADE, blank=True,
                                null=True, default=None)

    ground_truth = models.ForeignKey('project_ground_truth.GroundTruth', related_name='shares',
                                     on_delete=models.SET_NULL, blank=True, null=True)

    ground_truth_schema = models.ForeignKey('project_ground_truth.GroundTruthSchema',
                                            related_name='used_in_shares',
                                            on_delete=models.SET_NULL,
                                            blank=True, null=True)

    def __str__(self):
        return f'{self.name} ({self.identifier})'

    @staticmethod
    def import_share(**kwargs):
        # TODO maybe create an informational inboxmessageinfo class and object that states what is contained in that message (challenge, cases, projects, files)
        inbox_message: InboxMessage = kwargs.get('inbox_message')
        message: Message = kwargs.get('message')
        # set the recipient as created_by. is this correct?
        recipient_identifier = Profile.objects.filter_by_identifier(message.object.recipient)
        logging.info(f'Importing share for user {recipient_identifier}')
        if recipient_identifier is not None:
            created_by = recipient_identifier.first()
        else:
            created_by = get_user_node()

        content = message.object.content
        origin = Profile.objects.get_by_identifier(message.object.sender)
        logging.info('[start] importing share from %s', origin.identifier)
        # parse files first
        project_identifier = content.get('project')
        if project_identifier is not None:
            project = Project.objects.filter_by_identifier(project_identifier).first()
        else:
            project = None
        share_type = content.get('type')
        ident = identifier.from_string(content.get('identifier'))

        share = Share.objects.create(origin=origin,
                                     name=content.get('name', ''),
                                     description=content.get('description', ''),
                                     identifier=ident,
                                     content=content,
                                     project=project,
                                     created_by=created_by)
        ground_truth_schema_identifier = content.get('ground_truth_schema')
        if ground_truth_schema_identifier is not None:
            share.ground_truth_schema = GroundTruthSchema.objects.get_by_identifier(ground_truth_schema_identifier)

        with transaction.atomic():
            logging.info('[start] import cases')
            Case.import_case(cases=content.get('cases'),
                             project=project,
                             created_by=created_by,
                             origin=origin,
                             share=share)
            logging.info('[end] import cases')
            # file contains the case identifier, so import cases first.
            logging.info('[start] import files')
            File.import_file(files=content.get('files'),
                             project=project,
                             created_by=created_by,
                             origin=origin,
                             share=share,
                             for_user=inbox_message.recipient)
            logging.info('[end] import files')

            logging.info('[start] import codesystems')
            CodeSystem.import_codesystem(data=content.get('codesystems'), share=share)
            logging.info('[end] import codesystems')

            logging.info('[start] import codes')
            Code.import_codes(codes=content.get('codes'),
                              project=project,
                              created_by=created_by,
                              origin=origin,
                              share=share)
            logging.info('[end] import codes')
            logging.info('[start] import challenges')
            Challenge.import_challenge(challenge=content.get('challenge'), share=share)
            logging.info('[end] import challenges')
            logging.info('[start] import challenge datasets')
            Dataset.import_datasets(share=share, datasets=content.get('datasets'),
                                    datasets_files=content.get('datasets_files'),
                                    datasets_cases=content.get('datasets_cases'))
            logging.info('[end] import challenge datasets')
            logging.info('[start] import challenge target metrics')
            TargetMetric.import_metric(share=share, target_metrics=content.get('target_metrics'))
            logging.info('[end] import challenge target metrics')

            logging.info('[start] import evaluation code')
            EvaluationCode.import_evaluation_code(share=share, data=content.get('evaluation-code'))
            logging.info('[end] import evaluation code')

            pipeline = content.get('challenge_pipeline')
            if pipeline is not None:
                logging.info('[start] import challenge pipeline')
                # this is overwriting the current pipeline
                pipeline = ComputingPipeline.import_pipeline(created_by, pipeline)
                logging.info('[end] import challenge pipeline')

            if share_type == 'submission-part':
                # TODO is origin correct here??
                from apps.challenge.challenge_submission.models import Submission
                if pipeline is not None:
                    Challenge.import_data_files_for_stages(content.get('data_files'))

                    pipeline.is_template = True
                    pipeline.save(update_fields=['is_template'])
                Submission.create_submission(content.get('submission'), origin, part_submission=True)

                # TODO import the full computing pipeline here bc the identifiers of the computing job definitions are needed for the data files
                # computing pipeline is always a yaml

        logging.info('[start] import extra data')
        ExtraData.import_extra_data(share=share,
                                    project=project,
                                    for_user=inbox_message.recipient,
                                    extra_data=content.get('extra-data'))
        logging.info('[end] import extra data')

        Event.create(origin, Event.Verb.SHARE_RECEIVE, project, get_node_origin())
        logging.info('[end] importing share from %s', origin.identifier)

    @staticmethod
    def retract_share(**kwargs):
        logging.info('[start] retract share')
        message: Message = kwargs.get('message')
        content: RetractShareMessageContent = message.object.content
        share_identifier = content['identifier']

        # FIXME there are certain conditions when data cannot be retracted e.g. it was already published in a challenge.
        qs = Share.objects.filter(identifier=share_identifier)
        if qs.exists():
            Case.objects.filter(shares__in=list(qs)).delete()
            qs.first().delete()
        logging.info('[end] retract share')
