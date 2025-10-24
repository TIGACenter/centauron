from django.contrib import admin

from apps.computing.computing_log.models import ComputingJobLogEntry


class ComputingJobLogEntryAdmin(admin.ModelAdmin):
    list_display = ('identifier', 'computing_job', 'position', 'logged_at', 'date_created', 'content')
    ordering = ('-logged_at', '-date_created')


admin.site.register(ComputingJobLogEntry, ComputingJobLogEntryAdmin)
