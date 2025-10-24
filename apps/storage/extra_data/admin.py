from django.contrib import admin

from apps.storage.extra_data.models import ExtraData


class ExtraDataAdmin(admin.ModelAdmin):
    list_display = ('pk', 'application_identifier', 'date_created', 'origin', 'created_by')
    ordering = ('-date_created', )

admin.site.register(ExtraData, ExtraDataAdmin)
