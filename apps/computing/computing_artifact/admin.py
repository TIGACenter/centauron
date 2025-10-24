from django.contrib import admin

from apps.computing.computing_artifact.models import ComputingJobArtifact

class ComputingJobArtifactAdmin(admin.ModelAdmin):
    list_display = ('id', 'date_created', 'identifier', 'origin', 'file', 'computing_job')
    ordering = ('-date_created',)

admin.site.register(ComputingJobArtifact, ComputingJobArtifactAdmin)
