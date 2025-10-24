from django.urls import path

from apps.computing.computing_artifact import api
from apps.computing.computing_artifact.views import DownloadView

urlpatterns = [
    path('api/', view=api.ArtifactView.as_view(), name='api-artifact'),
    path('<uuid:challenge_pk>/<uuid:submission_pk>/<uuid:artefact_pk>/download/', view=DownloadView.as_view(), name='download')
]
