from typing import Any

from django.contrib import admin
from django.http import HttpRequest

from apps.study_management.models import Study, StudyArm


class StudyAdmin(admin.ModelAdmin):
    exclude = ('annotations', 'codes',)
    list_display = ('name', 'created_by', 'date_created')
    ordering = ['-date_created']

    def save_model(self, request: HttpRequest, obj, form: Any, change: Any) -> None:
        if obj.created_by is None:
            obj.created_by = request.user.profile
        super().save_model(request, obj, form, change)


admin.site.register(Study, StudyAdmin)


class StudyArmAdmin(admin.ModelAdmin):
    exclude = ('files', 'annotations', 'codes')
    list_display = ('pk', 'name', 'study')


admin.site.register(StudyArm, StudyArmAdmin)
