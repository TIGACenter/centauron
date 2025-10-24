from django.urls import path

from apps.user.user_profile.views import UpdateProfileView

app_name = 'user_profile'

urlpatterns = [
    path('form/', UpdateProfileView.as_view(), name='form'),
]
