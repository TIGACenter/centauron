from django.urls import include, path

urlpatterns = [
  path('execution/', include(('apps.computing.computing_executions.urls', 'computing_execution'))),
  path('artefact/', include(('apps.computing.computing_artifact.urls', 'computing_artefact'))),
]
