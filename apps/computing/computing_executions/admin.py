from django.contrib import admin

from apps.computing.computing_executions.models import ComputingJobExecution

class ComputingJobExecutionAdmin(admin.ModelAdmin):
    list_display = ('pk', 'identifier', 'date_created', )
    ordering = ('-date_created',)

admin.site.register(ComputingJobExecution, ComputingJobExecutionAdmin)
