import io
import logging
import uuid

import pandas
from django.db import models
from django.utils import timezone

from apps.core import db_utils
from apps.core.models import IdentifieableMixin, Base
from apps.user.user_profile.models import Profile


# Create your models here.


class ComputingJobLogEntry(IdentifieableMixin, Base):
    class Meta:
        ordering = ['position']

    class Type(models.TextChoices):
        OUTPUT = 'output'
        ERROR = 'error'
        INFO = 'info'

    type = models.CharField(choices=Type.choices, default=Type.OUTPUT, max_length=10)
    computing_job = models.ForeignKey('computing_executions.ComputingJobExecution', on_delete=models.CASCADE,
                                      related_name='log_entries')
    content = models.TextField(null=True)  # null = True so it can be updated loter when importing into challenge client
    position = models.PositiveIntegerField()
    logged_at = models.DateTimeField()

    @staticmethod
    def import_log(**kwargs):
        created_by: Profile | None = kwargs.get('created_by', None)
        entries = kwargs.get('logs', '')
        submission_id = kwargs.get('submission_id', None)
        if len(entries) == 0:
            logging.warning("No logs to import.")
            return

        df = pandas.read_csv(io.StringIO(entries))
        now = timezone.now().isoformat()
        df = df.rename(columns={'computing_job': 'computing_job_id'})
        job_cache = {}

        from apps.computing.computing_executions.models import ComputingJobExecution

        def fn(e):
            if e not in job_cache:
                job_cache[e] = ComputingJobExecution.objects.filter(identifier=e, definition__submission_id=submission_id).first().id_as_str
            return job_cache.get(e)

        df['computing_job_id'] = df['computing_job_id'].apply(fn)
        df['date_created'] = now
        df['last_modified'] = now
        df['id'] = df.apply(lambda e: str(uuid.uuid4()), axis=1)

        db_utils.insert_with_copy_from_and_tmp_table(df, ComputingJobLogEntry.objects.model._meta.db_table)
