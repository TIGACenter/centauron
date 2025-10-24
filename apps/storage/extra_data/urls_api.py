from django.urls import path

from apps.storage.extra_data import api

urlpatterns = [
    # path('annotation_backend/', api.CreateExtraDataForAnnotationBackendView.as_view(), name='create-from-annotation-backend')
    path('annotation_backend/', api.CreateExtraDataForAnnotationBackendViewSet.as_view({'post':'create'}), name='create-from-annotation-backend')
]
