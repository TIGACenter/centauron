from django.db import models
from django.urls import reverse

from apps.core.managers import BaseManager
from apps.core.models import BaseResource, CreatedByMixin

class StudyManager(BaseManager):
    pass

class Study(CreatedByMixin, BaseResource):
    objects = StudyManager()

    name = models.CharField(max_length=500)
    # terms = models.ManyToManyField('core.Concept', blank=True, related_name='studies')

    def get_absolute_url(self):
        return reverse('study_management:detail', kwargs=dict(pk=self.pk))

    def __str__(self):
        return self.name

class StudyArm(BaseResource):
    study = models.ForeignKey(Study, on_delete=models.CASCADE, related_name='arms')
    name = models.CharField(max_length=500)
    files = models.ManyToManyField('storage.File', blank=True, related_name='study_arms')


    def get_absolute_url(self):
        return reverse('study_management:arm-detail', kwargs=dict(pk=self.study.pk, arm_pk=self.pk))

    def __str__(self):
        return self.name
