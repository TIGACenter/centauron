from django.urls import path

from apps.terminology import views
from apps.terminology.api import TerminologyLookupView

urlpatterns = [
    path('add/', views.TerminologyDialogAddView.as_view(), name='dialog-add'),
    path('search/', views.CodeSearch.as_view(), name='search'),
    path('api/search/', TerminologyLookupView.as_view(), name='api-search'),
]
