import logging
from typing import Any

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404
from django.views.generic import TemplateView

from apps.storage.models import File


# LoginRequiredMixin not required because of hub functionality
class BaseViewer(TemplateView):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.object = None

    def get_queryset(self):
        return getattr(self, 'queryset')

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        ctx['object'] = self.get_object()
        ctx['iipsrv_url'] = settings.IIPSRV_URL
        return ctx

    def get_object(self):
        if self.object is not None:
            return self.object
        try:
            self.object = self.get_queryset().get(pk=self.kwargs['pk'])
            return self.object
        except:
            logging.error('Entity not found.')
            raise Http404()

    def get_template_names(self) -> list[str]:
        return [getattr(self, 'template')]


class SelectViewerView(LoginRequiredMixin, TemplateView):
    template_name = 'viewer/select.html'

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        ctx['object'] = File.objects.get(pk=self.kwargs['pk'])
        ctx['viewers'] = settings.VIEWER_APP_MAPPING
        return ctx
