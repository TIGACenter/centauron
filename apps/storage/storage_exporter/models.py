from django.db import models

from apps.core.models import Base, CreatedByMixin


class ExportJob(CreatedByMixin, Base):
    class Status(models.TextChoices):
        FAILURE = 'FAILURE'
        PENDING = 'PENDING'
        RUNNING = 'RUNNING'
        SUCCESS = 'SUCCESS'

    celery_task_id = models.CharField(max_length=50, null=True)
    status = models.CharField(choices=Status.choices, default=Status.PENDING, max_length=15)
    progress = models.FloatField(default=0.0)
    files = models.ManyToManyField('storage.File', blank=True)
    project = models.ForeignKey('project.Project', on_delete=models.SET_NULL, null=True)
    study = models.ForeignKey('study_management.Study', on_delete=models.SET_NULL, null=True)
    challenge = models.ForeignKey('challenge.Challenge', on_delete=models.SET_NULL, null=True)
    export_folder = models.CharField(max_length=1000, null=False)

