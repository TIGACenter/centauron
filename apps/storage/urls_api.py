from django.urls import path, include

from apps.storage import api

urlpatterns = [
    path('file/', api.CreateFileAPI.as_view(), name='api-storage-create'),
    path('extra_data/', include(('apps.storage.extra_data.urls_api', 'extra_data')))
]
