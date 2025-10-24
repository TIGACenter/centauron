import io
import uuid
from pathlib import Path

import pandas
from django.conf import settings
from django.core.paginator import Paginator
from django.db import models
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.computing.computing_executions.managers import ComputingJobExecutionManager
from apps.core import identifier, db_utils
from apps.core.models import CreatedByMixin, IdentifieableMixin, Base
from apps.user.user_profile.models import Profile


class ComputingJobExecution(CreatedByMixin, IdentifieableMixin, Base):
    objects = ComputingJobExecutionManager()

    class Status(models.TextChoices):
        RUNNING = 'running'
        PENDING = 'pending'
        ERROR = 'error'
        SUCCESS = 'success'
        CREATED = 'created'
        CREATING = 'creating'
        PREPARING = 'preparing'
        FAILED = 'failed'
        ACCEPTED = 'accepted'
        REJECTED = 'rejected'
        ACCEPTANCE_PENDING = 'acceptance_pending'
        KILLED = 'killed'

    definition = models.ForeignKey('computing.ComputingJobDefinition', on_delete=models.CASCADE,
                                   related_name='executions')
    executed = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    started_at = models.DateTimeField(null=True, default=None, blank=True)
    finished_at = models.DateTimeField(null=True, default=None, blank=True)
    k8s_data = models.JSONField(default=dict, blank=True)
    error = models.TextField(null=True, default=None, blank=True)
    batch_number = models.IntegerField(default=-1)
    executed_before = models.ForeignKey('ComputingJobExecution', on_delete=models.SET_NULL, null=True,
                                        related_name='executed_after', blank=True)
    input = models.ManyToManyField('storage.File', blank=True)

    def get_log(self):
        return self.log_entries.order_by('position')

    @property
    def has_error(self):
        return self.status == ComputingJobExecution.Status.ERROR

    @property
    def is_created(self):
        return self.status == ComputingJobExecution.Status.CREATED

    @property
    def is_preparing(self):
        return self.status == ComputingJobExecution.Status.PREPARING

    @property
    def is_creating(self):
        return self.status == ComputingJobExecution.Status.CREATING

    @property
    def is_failed(self):
        return self.status == ComputingJobExecution.Status.FAILED

    @property
    def is_running(self):
        return self.status == ComputingJobExecution.Status.RUNNING

    @property
    def is_success(self):
        return self.status == ComputingJobExecution.Status.SUCCESS

    @property
    def is_pending(self):
        return self.status == ComputingJobExecution.Status.PENDING

    @property
    def k8s_pod_name(self):
        return self.k8s_data.get('pod_name', None)

    def set_k8s_pod_name(self, pod_name):
        self.k8s_data['pod_name'] = pod_name

    @property
    def has_artefacts(self):
        return self.artifacts.exists()

    def get_tmp_dir(self, for_k8s=False):
        base = settings.COMPUTING_K8S_TMP_DIRECTORY if for_k8s else settings.HOST_K8S_TMP_DIRECTORY
        return base / f'{self.id_as_str}'

    @property
    def has_files(self):
        return self.definition.input is not None and len(self.definition.input) > 0

    @property
    def artifact_path(self) -> Path:
        return settings.COMPUTING_ARTIFACT_DIRECTORY / Path(self.id_as_str)

    @staticmethod
    def from_definition(created_by, definition):
        from apps.computing.models import ComputingJobDefinition
        definition: ComputingJobDefinition = definition
        if definition.is_batched:
            paginator = Paginator(definition.data_entities, definition.batch_size)
            definition.total_batches = paginator.num_pages
            definition.save(update_fields=['total_batches'])

            for page in paginator:
                ex = ComputingJobExecution()
                ex.identifier = identifier.create_random('computing-job-execution')
                ex.definition = definition
                ex.created_by = created_by
                ex.batch_number = page.number - 1
                ex.save()
                ex.input.set(page.object_list)
                yield ex
        else:
            # TODO create as many executions according to batch_number
            ex = ComputingJobExecution()
            ex.identifier = identifier.create_random('computing-job-execution')
            ex.definition = definition
            ex.created_by = created_by
            ex.save()
            de = definition.data_entities
            if de is not None:
                ex.input.set(de)
            yield ex

    @staticmethod
    def import_execution(**kwargs):
        from apps.computing.models import ComputingJobDefinition
        created_by: Profile | None = kwargs.get('created_by', None)
        origin: Profile | None = kwargs.get('origin', None)
        entities = kwargs.get('executions', [])
        submission = kwargs.get('submission')

        df = pandas.read_csv(io.StringIO(entities))
        now = timezone.now().isoformat()
        df = df.rename(columns={'definition': 'definition_id'})

        definitions_cache = {}

        def fn(e):
            if e not in definitions_cache:
                definitions_cache[e] = ComputingJobDefinition.objects.filter(identifier=e, submission_id=submission.id).first().id_as_str
            return definitions_cache.get(e)

        df['definition_id'] = df['definition_id'].apply(fn)
        df['created_by_id'] = created_by.id_as_str
        # df['origin_id'] = origin.id_as_str
        df['date_created'] = now
        df['last_modified'] = now
        df['executed'] = True
        df['k8s_data'] = '{}'
        df['id'] = df.apply(lambda e: str(uuid.uuid4()), axis=1)

        db_utils.insert_with_copy_from_and_tmp_table(df, ComputingJobExecution.objects.model._meta.db_table)

        submission = kwargs.get('submission')
        if submission is not None:
            # add computing job execution to submission
            df_s_cj = df[['id']].rename(columns={'id': 'computingjobexecution_id'})
            df_s_cj['submission_id'] = submission.id_as_str
            from apps.challenge.challenge_submission.models import Submission
            db_utils.insert_with_copy_from_and_tmp_table(df_s_cj, Submission.computing_job_executions.through.objects.model._meta.db_table,
                                                         insert_columns='computingjobexecution_id, submission_id')


        return list(df['id'])

        # TODO add to share?
