from django.conf import settings
from django.urls import path

from apps.challenge.challenge_client import views

urlpatterns = [
    path('', views.ChallengeListView.as_view(), name='challenge-list'),
    path('<uuid:pk>/enroll/', views.EnrollInChallengeView.as_view(), name='challenge-enroll'),
    path('<uuid:pk>/enroll/not/', views.NotEnrolledTemplateView.as_view(), name='challenge-not-enrolled'),
    path('<uuid:pk>/', views.ChallengeDetailView.as_view(), name='challenge-detail'),
    path('<uuid:pk>/datasets/', views.ChallengeDatasetsView.as_view(), name='challenge-datasets'),
    path('<uuid:pk>/exports/<uuid:job_pk>/', views.ExportDetailView.as_view(), name='challenge-datasets-exports-detail'),
    path('<uuid:pk>/exports/<uuid:job_pk>/actions/', views.ExportDetailActionsView.as_view(),
         name='challenge-datasets-exports-detail-actions'),
    path('<uuid:pk>/exports/', views.ExportListView.as_view(), name='challenge-datasets-exports'),
    path('<uuid:pk>/datasets/overview/', views.ChallengeDatasetsOverviewView.as_view(),
         name='challenge-datasets-overview'),
    path('<uuid:pk>/datasets/<uuid:dataset_pk>/', views.ChallengeDatasetsDetailView.as_view(),
         name='challenge-datasets-detail'),
    path('<uuid:pk>/datasets/<uuid:dataset_pk>/actions/', views.ChallengeDatasetsDetailActionView.as_view(),
         name='challenge-datasets-detail-action'),
    path('<uuid:pk>/submissions/', views.ChallengeSubmissionsListView.as_view(), name='challenge-submission-list'),
    path('<uuid:pk>/submissions/create/', views.ChallengeSubmissionCreateView.as_view(),
         name='challenge-submission-create'),
    path('<uuid:pk>/submissions/<uuid:submission_pk>/', views.ChallengeSubmissionsDetailView.as_view(),
         name='challenge-submission-detail'),
    path('<uuid:pk>/submissions/<uuid:submission_pk>/results/<uuid:status_pk>/',
         views.ChallengeResultDetailView.as_view(), name='challenge-submission-result-detail'),
    path('<uuid:pk>/leaderboard/', views.ChallengeLeaderboardView.as_view(), name='challenge-leaderboard'),
    path('<uuid:pk>/log/', views.LogView.as_view(), name='log'),
    path('<uuid:pk>/<uuid:submission_pk>/artifact/', views.ArtefactView.as_view(), name='artifact'),
]

if settings.HUB_ENABLE_REGISTRATION:
    urlpatterns += [
    path('register/', views.RegisterView.as_view(), name='register'),
    path('register/success/', views.RegisterSuccessView.as_view(), name='register_success'),
]
