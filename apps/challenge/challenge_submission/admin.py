from django.contrib import admin

from apps.challenge.challenge_submission.models import Submission, SubmissionStatus, SubmissionLogEntry, \
    SubmissionArtefact, TargetMetricValue, SubmissionToNodes


class SubmissionAdmin(admin.ModelAdmin):
    list_display = ('name', 'submitter', 'origin', 'challenge', 'date_created')
    list_display_links = ('name',)
    ordering = ('-date_created',)


admin.site.register(Submission, SubmissionAdmin)
admin.site.register(SubmissionStatus)


class SubmissionLogEntryAdmin(admin.ModelAdmin):
    list_display = ('pk', 'log_entry', 'sent', 'obscure', 'date_created')
    ordering = ('-date_created',)

admin.site.register(SubmissionLogEntry, SubmissionLogEntryAdmin)
admin.site.register(SubmissionArtefact)
admin.site.register(TargetMetricValue)


class SubmissionToNodesAdmin(admin.ModelAdmin):
    list_display = ('pk', 'submission', 'node', 'status', 'date_created')


admin.site.register(SubmissionToNodes, SubmissionToNodesAdmin)
