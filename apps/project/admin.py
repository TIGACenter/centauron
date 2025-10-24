from django.contrib import admin

from apps.core import identifier
from apps.event.models import Event
from apps.project.models import Project, DataView, ProjectMembership, FilePermission, ProjectExtraData


class ProjectAdmin(admin.ModelAdmin):
    exclude = ('files',)
    list_display = ('pk', 'name', 'codeset', 'origin', 'date_created')

    def get_form(self, request, obj, *args, **kwargs):
        form = super().get_form(request, obj, *args, **kwargs)
        form.base_fields['identifier'].initial = identifier.create_random('project')
        form.base_fields['created_by'].initial = request.user.profile
        form.base_fields['origin'].initial = request.user.profile
        return form

    def save_model(self, request, obj, form, change, **kwargs):
        if not change:
            R = super().save_model(request, obj, form, change)
            DataView.objects.create(created_by=request.user.profile,
                                    project=obj,
                                    name='Files',
                                    datatable_config={"columns": [{"data": "name", "title": "Name"},
                                                                  {"data": "date_created", "title": "Created at"},
                                                                  {"data": "origin", "title": "Origin"},
                                                                  {"data": "imported", "title": "Imported"},
                                                                  ]},
                                    model=DataView.Model.FILE)
            ProjectMembership.objects.create(user=obj.created_by, project=obj)
            Event.create(obj.origin, Event.Verb.PROJECT_CREATE, obj, obj)
        else:
            R = super().save_model(request, obj, form, change)
        return R


admin.site.register(Project, ProjectAdmin)
admin.site.register(DataView)

@admin.register(FilePermission)
class FilePermissionAdmin(admin.ModelAdmin):
    list_display = ('file', 'project', 'user', 'date_created', 'imported')
    ordering = ('-date_created',)

@admin.register(ProjectExtraData)
class ProjectExtraDataAdmin(admin.ModelAdmin):
    list_display = ('extra_data', 'project', 'user', 'date_created', 'imported')
    ordering = ('-date_created',)


@admin.register(ProjectMembership)
class ProjectMembershipAdmin(admin.ModelAdmin):
    list_display = ('pk', 'user', 'project', 'date_created')

