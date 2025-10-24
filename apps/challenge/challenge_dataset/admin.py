from typing import Any

from django.contrib import admin

from apps.challenge.challenge_dataset.models import Dataset, EvaluationCode
from apps.core import identifier


class DatasetAdmin(admin.ModelAdmin):
    exclude = ('files', 'cases',)
    list_display = ('name', 'challenge', 'date_created')
    ordering = ('-date_created',)

admin.site.register(Dataset, DatasetAdmin)


class EvaluationCodeAdmin(admin.ModelAdmin):

    list_display = ('name', 'identifier', 'challenge', 'schema', 'entrypoint', 'date_created')
    list_display_links = ('name',)
    ordering = ('date_created',)

    def save_model(self, request, obj, form: Any, change: Any) -> None:
        instance = form.save(commit=False)
        if instance._state.adding:
            instance.identifier = identifier.create_random('evaluation-code')
        instance.save()
        return instance

admin.site.register(EvaluationCode, EvaluationCodeAdmin)

