from django.urls import path

from apps.viewer.wsi.views import WsiViewerTemplate

urlpatterns = [
    path('', WsiViewerTemplate.as_view(), name='viewer')
]
