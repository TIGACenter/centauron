from django.contrib import admin

from apps.project.project_case.models import Case


class CaseAdmin(admin.ModelAdmin):
    list_display = ('name', 'date_created', 'get_projects', 'identifier', 'origin')
    list_display_links = ('name',)
    ordering = ('-date_created',)
    @admin.display(description='projects')
    def get_projects(self, o: Case):
        return ', '.join(o.projects.values_list('name', flat=True))


admin.site.register(Case, CaseAdmin)
