from django.urls import path
from rest_framework.routers import SimpleRouter

from apps.federation.file_transfer import views

router = SimpleRouter()


urlpatterns = [
    path('download/', views.FileServeView.as_view(), name='download')
]
