from django.contrib import admin

from apps.study_management.import_data.models import ImportJob


class ImportJobAdmin(admin.ModelAdmin):
    list_display = ('pk', 'file', 'celery_task_id',)
    ordering = ('-date_created', )

admin.site.register(ImportJob, ImportJobAdmin)
