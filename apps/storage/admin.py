from django.contrib import admin

from apps.storage.models import File


class FileAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'date_created', 'identifier', 'original_path', 'original_filename', 'path')
    ordering = ('-date_created',)
    search_fields = ('path', 'name', 'case__name', 'original_path', 'original_filename')


admin.site.register(File, FileAdmin)
