from django.contrib import admin

from apps.core import identifier
from apps.project.project_ground_truth.models import GroundTruthSchema, GroundTruth


class GroundTruthSchemaAdmin(admin.ModelAdmin):

    list_display = ('pk', 'name', 'identifier', 'project', 'date_created')
    ordering = ('-date_created',)

    def get_form(self, request, obj, *args, **kwargs):
        form = super().get_form(request, obj, *args, **kwargs)
        form.base_fields['identifier'].initial = identifier.create_random('ground-truth')
        form.base_fields['created_by'].initial = request.user.profile
        return form

admin.site.register(GroundTruthSchema, GroundTruthSchemaAdmin)

class GroundTruthAdmin(admin.ModelAdmin):
    list_display = ('pk','date_created')
    ordering = ('-date_created',)


admin.site.register(GroundTruth, GroundTruthAdmin)
