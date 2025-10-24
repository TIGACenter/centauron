from django.urls import path, include

urlpatterns = [
    path('<uuid:pk>/', include('apps.study_management.tile_management.urls_api'))
]
