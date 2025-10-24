from django.urls import path

from apps.core.views import IndexView

urlpatterns = [
    path('', IndexView.as_view(), name='index')
]
