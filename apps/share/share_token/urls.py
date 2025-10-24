from django.urls import path

from apps.share.share_token import views

urlpatterns = [
    path('<uuid:pk>/create/', views.CreateView.as_view(), name='dialog-create'),
    path('<uuid:pk>/action', views.ShareTokenActionView.as_view(), name='action')
]
