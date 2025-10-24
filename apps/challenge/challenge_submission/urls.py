from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.challenge.challenge_submission import datatables, views

router = DefaultRouter()
router.register(r'submissions', datatables.SubmissionDataTableView, basename='submission')

urlpatterns = [
                  path('', views.ListView.as_view(), name='list'),
                  path('<uuid:submission_pk>/', views.DetailView.as_view(), name='detail'),
                  path('<uuid:submission_pk>/<uuid:execution_pk>/export-artifacts/', views.ExportArtifactsView.as_view(), name='export-artifacts'),
                  path('<uuid:submission_pk>/<uuid:execution_pk>/log/', views.ExportLogView.as_view(), name='export-log'),
                  path('<uuid:submission_pk>/distribute/', views.DistributeSubmissionView.as_view(), name='distribute'),
                  path('<uuid:submission_pk>/pyscript/', views.SubmissionManualTaskPyScriptEnvView.as_view(),
                       name='pyscript'),
                  path('<uuid:submission_pk>/pyscript/store/',
                       views.SubmissionManualTaskPyScriptEnvStoreResultsView.as_view(), name='pyscript-store'),
                  path('<uuid:submission_pk>/<uuid:definition_pk>/<uuid:execution_pk>/send/',
                       views.SubmissionSendView.as_view(), name='send'),
                  path('<uuid:submission_pk>/send_aggregated/',
                       views.SubmissionSendAggregatedView.as_view(), name='send-aggregated'),

                path('<uuid:submission_pk>/<uuid:definition_pk>/<uuid:execution_pk>/send/logs/',
                       views.SubmissionSendPartialLogView.as_view(), name='send-logs'),
                  path('<uuid:submission_pk>/<uuid:definition_pk>/<uuid:execution_pk>/send/artefacts/',
                       views.SubmissionSendPartialArtefactsView.as_view(), name='send-artefacts'),
                  path('<uuid:submission_pk>/artifact/<uuid:artifact_pk>/', views.DownloadArtifactView.as_view(),
                       name='download-artifact'),

                  # path('create/', views.CreateView.as_view(), name='create'),
                  # path('<uuid:dataset_pk>/', views.DetailView.as_view(), name='detail'),
                  # path('<uuid:dataset_pk>/import/', views.ImportFromProjectView.as_view(), name='import'),
                  # path('<uuid:dataset_pk>/', include(router_files.urls)),
              ] + router.urls
