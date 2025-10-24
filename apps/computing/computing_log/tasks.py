import logging

from celery import shared_task
from django.utils import timezone

from apps.computing.computing_executions.models import ComputingJobExecution
from apps.computing.computing_log.models import ComputingJobLogEntry
from apps.core import identifier


@shared_task
def persist_log(job_pk, line, position, type):
    logging.info('Adding new log from stage.')
    job = ComputingJobExecution.objects.get(pk=job_pk)
    if not ComputingJobLogEntry.objects.filter(computing_job=job, position=position, content=line).exists():
        ComputingJobLogEntry.objects.create(computing_job=job, position=position, content=line, type=type,
                                                  logged_at=timezone.now(),
                                                  identifier=identifier.create_random('log'))
