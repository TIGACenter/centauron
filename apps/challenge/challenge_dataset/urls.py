from django.urls import path, include
from rest_framework.routers import DefaultRouter

from apps.challenge.challenge_dataset import datatables, views

router = DefaultRouter()
router.register(r'datasets', datatables.DatasetDataTableView, basename='dataset')

router_files = DefaultRouter()
router_files.register(r'files', datatables.FileDataTableView, basename='file')

urlpatterns = [
                  path('', views.ListView.as_view(), name='list'),
                  path('create/', views.CreateView.as_view(), name='create'),
                  path('<uuid:dataset_pk>/', views.DetailView.as_view(), name='detail'),
                  path('<uuid:dataset_pk>/update/', views.UpdateDatasetFormView.as_view(), name='update'),
                  path('<uuid:dataset_pk>/action/', views.FileTableActionView.as_view(), name='table-action'),
                  path('<uuid:dataset_pk>/import/', views.ImportFromProjectView.as_view(), name='import'),
                  path('<uuid:dataset_pk>/import/csv/', views.ImportDataCSVView.as_view(), name='import_csv'),
                  path('<uuid:dataset_pk>/', include(router_files.urls)),
                  # path('<uuid:dataset_pk>/ground_truth/', views.GroundTruthView.as_view(), name='ground_truth'),
                  path('<uuid:dataset_pk>/query/', view=views.QueryView.as_view(), name='project-query'),
                  path('<uuid:dataset_pk>/export/', view=views.ExportAsCSVView.as_view(), name='export'),

              ] + router.urls
