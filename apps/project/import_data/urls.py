from django.urls import path

from apps.project.import_data import views

urlpatterns = [
    path('csv/', views.ImportDataView.as_view(), name='csv'),
    path('node/', views.ImportFromNodeView.as_view(), name='node'),
    path('exact/', view=views.ImportAnnotationsFromExactView.as_view(), name='exact'),
    path('<str:celery_task_id>', views.ImportJobView.as_view(), name='import-job'),
    path('add-data/', view=views.AddDataToProjectQueryView.as_view(), name='add-data'),

]
