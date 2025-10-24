from django.urls import path

from apps.project.project_ground_truth.views import GroundTruthSchemaView, SendToCollaboratorsView, \
    GroundTruthSchemaDetailView

app_name = 'ground_truth'
urlpatterns = [
    path('schema/', GroundTruthSchemaView.as_view(), name='ground-truth-schema'),
    path('schema/<uuid:gt_pk>/', GroundTruthSchemaDetailView.as_view(), name='ground-truth-schema-detail'),
    path('schema/send/', SendToCollaboratorsView.as_view(), name='send-to-collaborators')
]
