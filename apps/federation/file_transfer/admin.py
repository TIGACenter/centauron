from django.contrib import admin

from apps.federation.file_transfer.models import TransferItem, TransferJob, DownloadToken


class TransferItemAdmin(admin.ModelAdmin):
    list_display = ('pk', 'status', 'file', 'date_created')
    ordering = ('-date_created',)
    exclude = ('file',)


class TransferJobAdmin(admin.ModelAdmin):
    list_display = ('pk', 'project', 'date_created')
    ordering = ('-date_created',)


class DownloadTokenAdmin(admin.ModelAdmin):
    list_display = ('token', 'for_user', 'date_created', 'file')
    ordering = ('-date_created',)


admin.site.register(TransferItem, TransferItemAdmin)
admin.site.register(DownloadToken, DownloadTokenAdmin)
admin.site.register(TransferJob, TransferJobAdmin)
