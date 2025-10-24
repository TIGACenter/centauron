from pathlib import Path

from django.conf import settings
from django.db import models
from django.urls import reverse

from apps.core.models import Base, CreatedByMixin


class ImportJob(CreatedByMixin, Base):
    class Status(models.TextChoices):
        PENDING = 'pending'
        RUNNING = 'running'
        SUCCESS = 'success'
        FAILED = 'failed'

    study_arm = models.ForeignKey('study_management.StudyArm', on_delete=models.CASCADE, related_name='import_jobs')
    file = models.CharField(max_length=500, null=True)
    celery_task_id = models.CharField(max_length=500, null=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    message = models.TextField(blank=True, null=True)

    @property
    def file_path(self) -> Path:
        return settings.TMP_DIR / self.file

    # def __str__(self):
    def get_absolute_url(self):
        return reverse('study_management:import_data:detail',
                       kwargs=dict(job_pk=self.pk, arm_pk=self.study_arm.pk, pk=self.study_arm.study_id))
