from django.urls import path

from apps.challenge.challenge_leaderboard import views

urlpatterns = [
    path('', views.ListView.as_view(), name='list'),
    path('calculate/', views.CalculateLeaderboardView.as_view(), name='calculate'),
    path('send/', views.SendLeaderboardView.as_view(), name='send')
]
