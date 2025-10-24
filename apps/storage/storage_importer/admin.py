from django.contrib import admin

from apps.storage.storage_importer.models import ImportJob, ImportFolder

# Register your models here.
admin.site.register(ImportJob)

class ImportFolderAdmin(admin.ModelAdmin):
    list_display = ('pk', 'date_created', 'path', 'importing', 'imported', 'study', 'project',)
    ordering = ('-date_created',)
admin.site.register(ImportFolder, ImportFolderAdmin)
