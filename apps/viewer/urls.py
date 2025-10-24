from django.urls import path, include

from apps.viewer.views import SelectViewerView

urlpatterns = [
    path('<uuid:pk>/select/', SelectViewerView.as_view(), name='select'),
    path('<uuid:pk>/wsi/', include(('apps.viewer.wsi.urls', 'wsi'))),
    path('<uuid:pk>/image/', include(('apps.viewer.image.urls', 'image')))
]
