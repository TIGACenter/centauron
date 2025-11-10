from django.contrib import admin

from apps.project.website.models import ProjectWebsite


@admin.register(ProjectWebsite)
class ProjectWebsiteAdmin(admin.ModelAdmin):
    list_display = ('project', 'contact_email', 'date_created', 'last_modified')
    search_fields = ('project__name', 'contact_email')
    ordering = ('-date_created',)
