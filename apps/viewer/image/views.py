# Create your views here.
import logging
from typing import Any

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.views import View

from apps.storage.models import File
from apps.viewer.views import BaseViewer


class ImageViewerTemplate(BaseViewer):
    template = 'viewer/image/viewer.html'
    queryset = File.objects.filter(imported=True)

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        # TODO add a project context or so??
        annotations = self.object.extra_data.order_by(
            '-date_created')  # TODO only filter for extra data that are annotations or are created by an application with a specific application_identifier
        ctx['annotations'] = annotations
        return ctx


class ImageView(LoginRequiredMixin, View):
    def get(self, request, pk, *args, **kwargs):
        try:
            # TODO add user has access to file
            file:File = get_object_or_404(File, pk=pk, imported=True)
            # Open the image file in binary read mode

            with file.as_path.open('rb') as f:
                image_data = f.read()

            return HttpResponse(image_data, content_type=file.content_type)
        except Exception as e:
            logging.exception(e)
            return HttpResponse(f"An error occurred while serving the image: {e}", status=500)
