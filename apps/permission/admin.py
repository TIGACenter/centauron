from django.contrib import admin

from apps.permission.models import Permission


class PermissionAdmin(admin.ModelAdmin):
    list_display = ('object_identifier', 'action', 'permission', 'date_created')
    list_display_links = ('object_identifier',)
    ordering = ('-date_created',)


admin.site.register(Permission, PermissionAdmin)
