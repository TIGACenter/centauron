from django.urls import path, include

from apps.user.views import DashboardView

urlpatterns = [
    path('dashboard/', DashboardView.as_view(), name='dashboard'),
    path('profile/', include('apps.user.user_profile.urls', namespace='profile'))
]
