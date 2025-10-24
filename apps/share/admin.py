from django.contrib import admin

from apps.share.models import Share

class ShareAdmin(admin.ModelAdmin):
    list_display = ('pk', 'name', 'identifier', 'date_created')
    ordering = ('-date_created', )
    exclude = ('files', 'challenges', 'cases', 'datasets', 'computing_job_definitions', 'computing_job_executions',
               'computing_job_logs', 'computing_job_artefacts', 'codes')
    search_fields = ['identifier']

admin.site.register(Share, ShareAdmin)
