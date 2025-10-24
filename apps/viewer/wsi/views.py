from typing import Any

from apps.storage.models import File
from apps.viewer.views import BaseViewer


class WsiViewerTemplate(BaseViewer):
    template = 'viewer/wsi/viewer.html'
    queryset = File.objects.filter(imported=True)

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        # TODO add a project context or so??
        annotations = self.object.extra_data.order_by(
            '-date_created')  # TODO only filter for extra data that are annotations or are created by an application with a specific application_identifier
        ctx['annotations'] = annotations
        return ctx
