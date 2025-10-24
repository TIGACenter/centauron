from django.contrib import admin

from apps.storage.storage_exporter.models import ExportJob


class ExportJobAdmin(admin.ModelAdmin):
    ordering = ('-date_created',)
    list_display = ['pk', 'status', 'challenge']


admin.site.register(ExportJob, ExportJobAdmin)
