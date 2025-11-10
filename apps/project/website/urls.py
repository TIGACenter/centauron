from django.urls import path

from apps.project.website.views import CreateWebsiteView, PreviewView
app_name = 'website'

urlpatterns = [
    path('create/', view=CreateWebsiteView.as_view(), name='create'),
    path('<uuid:website_pk>/preview/', view=PreviewView.as_view(), name='preview'),
]
