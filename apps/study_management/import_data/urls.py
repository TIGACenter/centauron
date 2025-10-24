from django.urls import path

from apps.study_management.import_data import views

urlpatterns = [
    path('', views.ImportJobListView.as_view(), name='list'),
    path('import/preview/', views.ImportFormPreview.as_view(), name='form-preview'),
    path('import/', views.ImportFormView.as_view(), name='form'),
    path('<uuid:job_pk>/', views.ImportJobDetailView.as_view(), name='detail')

]
