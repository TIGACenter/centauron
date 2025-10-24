from django.urls import path

from apps.viewer.image.views import ImageViewerTemplate, ImageView

urlpatterns = [
    path('', ImageViewerTemplate.as_view(), name='viewer'),
    path('image/', ImageView.as_view(), name='image'),
]
