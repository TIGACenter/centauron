from django.conf import settings
from rest_framework.routers import DefaultRouter, SimpleRouter

from apps.project.api.views import ProjectViewSet

if settings.DEBUG:
    router = DefaultRouter()
else:
    router = SimpleRouter()

router.register('projects', ProjectViewSet, basename='projects')

app_name = "api"
urlpatterns = router.urls
