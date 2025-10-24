import json
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views.generic import FormView

from apps.share import forms, tasks
from apps.study_management.tile_management.models import TileSet


class CreateShareDialogView(LoginRequiredMixin, FormView):
    template_name = 'share/create-dialog.html'
    form_class = forms.CreateShareForm

    def get_initial(self) -> dict[str, Any]:
        ctx = {
            'valid_from': timezone.now(),
            'valid_until': timezone.now() + timedelta(days=30),
            'percentage': 20,
        }
        if settings.DEBUG: ctx['project_identifier'] = 'ak.dev.centauron.io#project::abc'
        return ctx

    def get_form_kwargs(self) -> dict[str, Any]:
        ctx = super().get_form_kwargs()
        ctx['object'] = self.request.GET.get('object', None)
        ctx['pk'] = self.request.GET.get('pk', None)
        return ctx

    def get_context_data(self, **kwargs):
        c = super().get_context_data(**kwargs)
        c.update({
            'codes': [dict(**e, id=str(e['pk'])) for e in
                         self.get_codes().values('pk', 'codesystem__name', 'code')]
        })
        return c

    def get_model(self):
        object = self.request.GET.get('object', None)
        if object == 'tileset':
            return TileSet

    def get_object(self):
        pk = self.request.GET.get('pk', None)
        return get_object_or_404(self.get_model(), pk=pk, created_by=self.request.user.profile)

    def get_codes(self):
        if self.get_model() == TileSet:
            return self.get_object().included_terms.all().prefetch_related('codesystem')

    def get_lookup_field(self):
        if self.get_model() == TileSet:
            return 'filesets'

    def form_valid(self, form):
        data = form.cleaned_data
        node = data.get('node')
        project_identifier = data.get('project_identifier')
        messages.success(self.request, f'Data will be shared with {node} in background.')
        model = 'file'
        if self.get_model() == TileSet:
            model = 'file'

        tree = json.loads(data.get('file_selector'))
        children1 = tree.get('children1')
        lookup_field = self.get_lookup_field()
        lookup_value = self.request.GET.get('pk', None)
        if children1 is not None:
            children1.append({
                    "type": "rule",
                    "id": "999ba8ab-0123-4456-b89a-b189883ff396",
                    "properties": {
                        "field": lookup_field,
                        "operator": "select_equals",
                        "value": [lookup_value],
                    }
            })

        tasks.create_share(
            self.request.GET.get('object', None),
            model,
            project_identifier,
            data.get('valid_from'),
            data.get('valid_until'),
            self.request.user.profile.id_as_str,
            node.id_as_str,
            json.dumps(tree), # to json for celery
            int(data.get('percentage'))
        )
        return redirect(self.request.META['HTTP_REFERER'])
