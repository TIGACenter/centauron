from django.urls import path
from apps.computing.computing_executions import api as api_views
from apps.computing.computing_executions.views import LogView

urlpatterns = [
    path('api/jobs/<uuid:pk>/log/', api_views.LogView.as_view(), name='api-log'),
    path('api/jobs/<uuid:pk>/artifact/', api_views.ArtifactView.as_view(), name='api-artifact'),
    path('api/jobs/<uuid:pk>/stage/', api_views.StageView.as_view(), name='api-stage'),
    path('jobs/<uuid:pk>/log/', LogView.as_view(), name='log')
]
