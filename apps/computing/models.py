import io
import logging
import uuid
from typing import Dict, Any

import docker
import pandas
import yaml
from celery import chain
from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.challenge.challenge_dataset.models import Dataset, EvaluationCode
from apps.computing import utils
from apps.computing.managers import ComputingJobTemplateManager, ComputingJobDefinitionManager
from apps.core import identifier, db_utils
from apps.core.models import Base, IdentifieableMixin, CreatedByMixin, OriginMixin
from apps.node.models import Node
from apps.project.project_ground_truth.models import GroundTruth
from apps.user.user_profile.models import Profile


# TODO write an execution backend for the computing job execution.
# pattern see here: https://charlesleifer.com/blog/django-patterns-pluggable-backends/
# K8SBackend, AlwaysSucceedBackend (for testing), AlwaysFailBackend (for testing). in the future maybe even a SlurmBackend


class ComputingJobTemplate(CreatedByMixin, OriginMixin, IdentifieableMixin, Base):
    objects = ComputingJobTemplateManager()
    template_fields = models.JSONField(default=list, blank=True)

    @staticmethod
    def import_template(created_by, origin, template: Dict[str, Any]):
        if template is None:
            return None
        fields = template.get('template_fields', [])
        id = template.get('identifier')

        qs = ComputingJobTemplate.objects.filter(identifier=id)
        if qs.exists():
            return qs.first()

        return ComputingJobTemplate.objects.create(template_fields=fields,
                                                   origin=origin,
                                                   created_by=created_by,
                                                   identifier=id)


class ComputingJobDefinition(CreatedByMixin, OriginMixin, IdentifieableMixin, Base):
    objects = ComputingJobDefinitionManager()

    class Type(models.TextChoices):
        TRAINING = 'training'
        VALIDATION = 'validation'

    class ExecutionType(models.TextChoices):
        MANUAL = 'manual'
        AUTO = 'auto'

    execution_type = models.CharField(max_length=6, choices=ExecutionType.choices, default=ExecutionType.AUTO)
    namespace = models.CharField(max_length=63, blank=True)
    name = models.CharField(max_length=200, blank=True)
    # can be null if a template is used
    docker_image = models.CharField(max_length=500, null=True, blank=True)
    result = models.JSONField(default=dict, null=True, blank=True)
    # k8s_data = models.JSONField(default=dict, blank=True)
    k8s_spec = models.JSONField(null=True, default=None, blank=True)
    output = models.JSONField(default=list, blank=True)  # file output
    input = models.JSONField(default=list, blank=True)  # file input
    type = models.CharField(max_length=20, choices=Type.choices, default=Type.TRAINING)
    entrypoint = models.JSONField(null=True, default=None, blank=True)  # needs to be a list
    retagged_docker_image = models.CharField(max_length=500, null=True, blank=True, default=None)
    credentials = models.JSONField(default=None, null=True, blank=True)
    # may be null if used by a
    pipeline = models.ForeignKey('ComputingPipeline', on_delete=models.CASCADE, related_name='stages', null=True,
                                 blank=True)
    position = models.IntegerField(default=1)
    template = models.OneToOneField(ComputingJobTemplate, blank=True, null=True, on_delete=models.SET_NULL,
                                    related_name='definition')
    resources = models.JSONField(null=True, blank=True, default=None)
    data_file = models.CharField(max_length=500, null=True, blank=True)
    dataset = models.ForeignKey('challenge_dataset.Dataset', null=True, blank=True, on_delete=models.SET_NULL)
    batch_size = models.IntegerField(blank=True, default=-1)
    total_batches = models.IntegerField(blank=True, default=-1)

    copied_from = models.ForeignKey('ComputingJobDefinition', null=True, blank=True, on_delete=models.CASCADE)
    submission = models.ForeignKey('challenge_submission.Submission', null=True, blank=True, on_delete=models.SET_NULL)
    environment_variables = models.JSONField(default=dict, blank=True, null=True)
    # variables can be added here that are then converted to query params for API calls for registering log and artefacts.
    environment_variables_job_context = models.JSONField(default=dict, blank=True, null=True)
    args = models.JSONField(default=dict, blank=True, null=True)

    # all the users that have data in data_file
    data_origins = models.ManyToManyField('user_profile.Profile', blank=True)

    def __str__(self):
        return f'{self.name} - {self.docker_image} ({self.type})'

    @property
    def execution_type_is_auto(self):
        return self.execution_type == ComputingJobDefinition.ExecutionType.AUTO

    @property
    def is_label_crossing_job(self):
        return self.entrypoint is not None and 'evaluation-code' in self.entrypoint.strip()

    @property
    def is_batched(self):
        return self.batch_size > 0

    @property
    def has_datafile(self):
        return self.data_file is not None and len(self.data_file.strip()) > 0

    @property
    def has_template(self):
        return self.template is not None

    @property
    def has_credentials(self):
        return self.credentials is not None and len(self.credentials.strip()) > 0

    @property
    def has_input(self):
        return self.input is not None and len(self.input) > 0

    @property
    def is_training_job(self):
        return self.type == ComputingJobDefinition.Type.TRAINING

    @property
    def is_validation_job(self):
        return self.type == ComputingJobDefinition.Type.VALIDATION

    @property
    def is_post(self):
        return self.name == '.post'

    @property
    def data_entities(self):
        if self.dataset is not None:
            return self.dataset.files.all()  # dataset needs to be present in this job definition or it cannot be processed. this also means that the .post stage cannot be batched as there is no dataset but just a single file.
        else:
            return None

    @staticmethod
    def import_(created_by, origin, stage: Dict[str, Any]):
        template = stage.get('template')
        # if template is None:
        #     return None
        name = stage.get('name')
        id = stage.get('identifier')
        entrypoint = stage.get('entrypoint', None)
        docker_image = stage.get('docker_image')
        execution_type = stage.get('execution_type', ComputingJobDefinition.ExecutionType.AUTO)
        input = stage.get('input', [])
        output = stage.get('output', [])
        position = stage.get('position', 1)
        credentials = stage.get('credentials')

        qs = ComputingJobDefinition.objects.filter(identifier=id)
        if qs.exists():
            return qs.first()
        return ComputingJobDefinition.objects.create(
            name=name,
            created_by=created_by,
            identifier=id,
            origin=origin,
            entrypoint=entrypoint,
            docker_image=docker_image,
            execution_type=execution_type,
            input=input,
            output=output,
            position=position,
            credentials=credentials,
            template=ComputingJobTemplate.import_template(created_by, origin, template)
        )

    @staticmethod
    def import_definition(**kwargs):
        from apps.challenge.challenge_submission.models import Submission
        created_by: Profile | None = kwargs.get('created_by', None)
        origin: Profile | None = kwargs.get('origin', None)
        entities = kwargs.get('definitions', '')
        submission_reference = kwargs.get('submission_reference')
        submission = kwargs.get('submission')

        df = pandas.read_csv(io.StringIO(entities))
        now = timezone.now().isoformat()
        df = df.rename(columns={'submission': 'submission_id'})
        submission_cache = {}

        def fn(e):
            f = e
            if submission_reference is not None:
                f = submission_reference
            if f not in submission_cache:
                try:
                    submission_cache[f] = Submission.objects.get_by_identifier(f).id_as_str
                except Submission.DoesNotExist:
                    submission_cache[f] = submission.id_as_str
                # submission_cache[f] = Submission.objects.get_by_identifier(f, origin__isnull=True).id_as_str
            return submission_cache.get(f)

        # identifiers = df['identifier'].to_list()
        # qs = ComputingJobDefinition.objects.filter(identifier__in=identifiers, pipeline__is_template=False).distinct()
        # existing_files = {e[0]: e[1] for e in qs.values_list('identifier', 'id')}
        # existing_rows = df['identifier'].isin(existing_files.keys())
        # df['existing'] = existing_rows
        #
        # def fn_set_id(e):
        #     if not e['existing']: return str(uuid.uuid4())
        #     return existing_files[e['identifier']]
        #
        # df['id'] = df.apply(fn_set_id, axis=1)  # df.apply(lambda e: str(uuid.uuid4()), axis=1)
        # # filter out existing files
        # df = df[~existing_rows]

        df['submission_id'] = df['submission_id'].apply(fn)
        df['created_by_id'] = created_by.id_as_str
        df['origin_id'] = origin.id_as_str
        df['date_created'] = now
        df['last_modified'] = now
        df['id'] = df.apply(lambda e: str(uuid.uuid4()), axis=1)
        df['namespace'] = ''
        df['output'] = '[]'
        df['input'] = '[]'
        df['type'] = ''
        df['position'] = 0

        if len(df.index) > 0:
            db_utils.insert_with_copy_from_and_tmp_table(df, ComputingJobDefinition.objects.model._meta.db_table)
        # TODO add to share?

    @property
    def has_executions(self):
        return self.executions.exists()

    def execute(self, created_by_pk, submission_pk=None):
        from apps.computing.tasks import start_task_from_computing_definition
        from apps.computing.tasks import send_submission_run_event

        chain(start_task_from_computing_definition.s(created_by_pk=created_by_pk, computing_definition_pk=self.id_as_str, submission_pk=submission_pk),
              send_submission_run_event.si(computing_definition_pk=self.id_as_str, submission_pk=submission_pk)).apply_async()

    def get_docker_image_name_and_tag(self, image_name):
        if ':' in image_name:
            image, tag = image_name.split(':')
        else:
            image, tag = image_name, 'latest'

        path = ''
        if '/' in image:
            s = image.split('/')
            parts = s[1:-1]
            if len(parts) > 0:
                path = '/'.join(parts) + '/'

            image = s[-1]

        return image, tag, path

    def push_and_pull_docker_image_to_private_repository(self, job: 'ComputingJobDefinition'):
        if job.docker_image is None:
            logging.warning('No docker image provided for job %s', job)
            return

        image, tag, path = self.get_docker_image_name_and_tag(job.docker_image)
        retag = job.docker_image
        if settings.RETAG_DOCKER_IMAGES:
            docker_client = docker.from_env()
            logging.info('Pulling docker image %s', job.docker_image)
            auth_config = {}
            if job.has_credentials:
                auth_config = dict(auth_config=dict(username=job.credentials.get('username', None),
                                                    password=job.credentials.get('password', None)))
            # pull docker image
            docker_client.images.pull(job.docker_image, tag=tag,
                                      **auth_config)  # TODO error handling of image does not exist.
            docker_image = docker_client.images.get(job.docker_image)
            # re-tag and include some random string in case of same image and tag is used by different user.
            tag = f'{uuid.uuid4()}-{tag}'
            retag = f'{settings.PRIVATE_DOCKER_REPOSITORY}/{path}{image}:{tag}'
            # TODO check if retagged docker image is already exists from a previous run and do not retag and repush.
            logging.info('Retagging docker image %s to %s', job.docker_image, retag)
            docker_image.tag(repository=retag, tag=tag)
            # push to private repository
            logging.info('Pushing docker image %s', retag)
            docker_client.images.push(retag, tag=tag)
        job.retagged_docker_image = retag
        job.save(update_fields=['retagged_docker_image'])

    @staticmethod
    def create_from_yml(
        *,
        origin,
        created_by,
        entrypoint,
        docker_image,
        output,
        input,
        batch_size,
        resources,
        position,
        template,
        data_file,
        dataset,
        pipeline,
        name,
        namespace,
        execution_type,
        env
    ):
        return ComputingJobDefinition.objects.create(
            created_by=created_by,
            origin=origin,
            identifier=identifier.create_random('computing-job-definition'),
            pipeline=pipeline,
            position=position,
            input=input,
            output=output,
            docker_image=docker_image,
            resources=resources,
            template=template,
            entrypoint=entrypoint,
            data_file=data_file,
            name=name,
            batch_size=batch_size,
            dataset=dataset,
            namespace=namespace,
            execution_type=execution_type,
            environment_variables=env
        )

    def next(self):
        return ComputingJobDefinition.objects.filter(pipeline=self.pipeline, position=self.position + 1).first()

    def previous(self):
        return ComputingJobDefinition.objects.filter(pipeline=self.pipeline, position=self.position - 1).first()

    @staticmethod
    def create_from_template(template: 'ComputingJobTemplate', pipeline: 'ComputingPipeline', fields):
        field_values = fields['template']
        c_def = pipeline.stages.filter(name=template.definition.name).first()
        for field in template.template_fields:
            # stage_name, field = field.split('.')
            if field == 'image':
                c_def.docker_image = field_values[field]
            if field == 'credentials':
                c_def.credentials = field_values[field]
            if field == 'script':
                c_def.entrypoint = field_values[field]
        c_def.save()
        return c_def

    def copy(self):  # , src:'ComputingJobDefinition'):
        src_id = self.id_as_str
        self.pk = None
        self.template = None
        # self.pipeline = self.pipeline
        self.save()
        self.copied_from_id = src_id
        self.save()
        return self

    @property
    def first_execution(self):
        return self.executions.first()


class ComputingPipeline(CreatedByMixin, OriginMixin, IdentifieableMixin, Base):
    # git_repository = models.URLField()
    # git_commit = models.CharField(max_length=40)
    name = models.CharField(max_length=200, default=utils._generate_random_name)
    error = models.TextField(null=True, default=None, blank=True)
    is_template = models.BooleanField(default=False)
    instantiated_from = models.ForeignKey('ComputingPipeline', on_delete=models.SET_NULL, null=True, blank=True)

    # template = models.BooleanField(default=False)
    # template_fields = models.JSONField(default=None, blank=True, null=True)

    # repository = models.ForeignKey('repository.Repository', on_delete=models.CASCADE, default=None, null=True)

    # def get_log_censored(self, include_sent_items=False):
    #     log = [
    #         f'[{e.logged_at.isoformat()} - {e.stage.definition.name}] {e.content}' if not e.dont_send else '[missing]\n'
    #         for e in
    #         self.log_entries.filter(sent=include_sent_items).prefetch_related('stage').order_by('position').all()]
    #     return ''.join(log)
    #
    # def get_absolute_url(self):
    #     return reverse('computing:detail', kwargs=dict(pk=self.pk))
    #
    # def __str__(self):
    #     return self.name

    def was_executed(self, current_user):
        # returns if the pipeline was not executed yet.
        # get the first stage and check if it has any executions that are not pending!
        from apps.computing.computing_executions.models import ComputingJobExecution
        # FIXME add created_by = current user
        return self.stages.first().executions.filter(created_by=current_user).exclude(status__in=[ComputingJobExecution.Status.PENDING]).exists()
        # return self.stages.first().executions.exclude(status__in=[ComputingJobExecution.Status.PENDING]).exists()

    def get_first_executable_stage(self):
        # FIXME if the stage at position = 0 is
        return self.stages.order_by('position').first()
        # for s in self.stages.order_by('position'):
        #     if not s.is_label_crossing_job:
        #         return s
        # return None

    def execute(self, created_by_pk: str, stage_definition_pk=None, submission_pk=None):
        if stage_definition_pk is None:
            stage = self.get_first_executable_stage()
        else:
            # TODO add executed_before to this stage?
            stage = self.stages.filter(pk=stage_definition_pk).first()

        if stage is None:
            logging.error('ComputingJobDefinition with pk=%s not found.', stage_definition_pk)
            return

        stage.execute(created_by_pk, submission_pk=submission_pk)

    @staticmethod
    def from_yml(created_by, origin, yml, k8s_namespace):
        c = yaml.safe_load(yml)
        pipeline = ComputingPipeline.objects.create(created_by=created_by,
                                                    is_template=True,
                                                    origin=origin,
                                                    identifier=identifier.create_random('computing-pipeline'))

        stages = c.get('stages', None)
        if stages is None:
            raise ValueError('No stages found (key: stages).')

        defs = []
        # filter out .post stage name as it is a reserved stage name for label-crossing
        # stages = list(filter(lambda e: e != '.post', stages))
        for idx, stage_name in enumerate(stages):
            stage = c.get(stage_name, None)
            if stage is None:
                raise ValueError(f'Stage {stage_name} was declared but not specified.')

            script = stage.get('script', [])
            image = stage.get('image', None)
            output = stage.get('output', [])
            input = stage.get('input', [])
            # batch_item = stage.get('data', None)
            batch_size = stage.get('batch_size', -1)
            # requires_data = stage.get('requires_data', False)
            resources = stage.get('resources', None)
            data = stage.get('data', None)
            template = stage.get('template', None)
            template_fields = stage.get('template_fields', None)
            execution_type = stage.get('type', 'auto')  # auto or manual
            env = stage.get('env', {})

            if not template:
                template = None

            if template is not None:
                if template_fields is None:
                    raise ValueError('template fields must be defined if stage is template.')
                template = ComputingJobTemplate.objects.create(
                    template_fields=template_fields,
                    origin=origin,
                    created_by=created_by,
                    identifier=identifier.create_random('computing-job-template')
                )

            execution_type_is_auto = execution_type == ComputingJobDefinition.ExecutionType.AUTO
            # if data is given: write identifiers and paths to file and only provide file path here.
            # this is to ensure that no data changes and runs are comparable
            data_file = None
            dataset = None
            data_origins = Profile.objects.none()

            if data is not None:
                if '#' in data:
                    # is execution_type == auto: identifier is a dataset
                    # is execution_type == manual: identifier is a ground truth
                    # if execution_type_is_auto:
                    # data is an identifier of a dataset
                    dataset = Dataset.objects.filter_by_identifier(data).first()
                    data_file = settings.STORAGE_DATA_DIR / str(uuid.uuid4())
                    dataset.write_files_to_csv(data_file)
                    data_file = data_file.relative_to(settings.STORAGE_DATA_DIR)
                    data_origins = Profile.objects.filter(
                        pk__in=dataset.files.values_list('origin', flat=True).distinct())
                # else:
                #     # check if ground truth exists
                #     # GroundTruth.objects.filter_by_identifier(data)  # TODO add challenge to query
                #     data_file = data
                else:
                    # data is a file TODO implement. this is the case for git repos
                    pass

            if not execution_type_is_auto:
                # check if script is the identifier of a code that belongs to this challenge
                EvaluationCode.objects.get_by_identifier(
                    identifier.from_string(script))  # TODO add challenge to query

            cjd = ComputingJobDefinition.create_from_yml(
                origin=origin,
                created_by=created_by,
                docker_image=image,
                entrypoint=script,
                input=input,
                output=output,
                position=idx,
                pipeline=pipeline,
                template=template,
                resources=resources,
                data_file=data_file,
                batch_size=batch_size,
                dataset=dataset,
                name=stage_name,
                namespace=k8s_namespace,
                execution_type=execution_type,
                env=env
            )
            cjd.data_origins.set(data_origins)
        return pipeline

    @staticmethod
    def import_pipeline(created_by, pipeline: Dict[str, Any]):
        stages = pipeline.get('stages', [])
        origin = Profile.objects.get_by_identifier(pipeline.get('origin'))
        p = ComputingPipeline.objects.create(created_by=created_by,
                                             origin=origin,
                                             identifier=pipeline.get('identifier'))

        from apps.challenge.models import Challenge
        Challenge.objects.filter_by_identifier(pipeline.get('challenge')).update(pipeline=p)

        for stage in stages:
            cjd = ComputingJobDefinition.import_(created_by, origin, stage)
            if cjd is not None:
                p.stages.add(cjd)

        return p

    @staticmethod
    def from_template(template: 'ComputingPipeline', created_by, challenge, submission):
        if not template.is_template:
            return None
        stages = list(template.stages.all())
        pipe_1 = template
        pipe_1.pk = None
        pipe_1.save()
        pipe_1.name = utils._generate_random_name()
        pipe_1.identifier = identifier.create_random('computing-pipeline')
        pipe_1.is_template = False
        pipe_1.challenge = challenge
        pipe_1.created_by = created_by
        pipe_1.instantiated_from = template

        for d in stages:
            d = d.copy()
            d.pipeline = pipe_1
            d.submission = submission
            # TODO if d.is_batched then create n amount of executions based on the stage
            d.save()
            # pipe_1.stages.add(d)
        pipe_1.save()

        return pipe_1
