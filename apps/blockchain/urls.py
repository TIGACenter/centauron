from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.blockchain import views, datatables

app_name = 'blockchain'

router = DefaultRouter()
router.register(r'logs', datatables.LogDataTableView, basename='logs')

urlpatterns = [
                  path('', views.ExplorerView.as_view(), name='explorer'),
                  path('network/', views.NetworkView.as_view(), name='network'),
              ] + router.urls
