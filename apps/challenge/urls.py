from django.urls import path, include

from apps.challenge import views

urlpatterns = [
    path('', views.ListView.as_view(), name='list'),
    path('create', views.CreateChallengeView.as_view(), name='create'),
    path('<uuid:pk>/', views.RedirectToDatasetListView.as_view(), name='detail'),
    path('<uuid:pk>/update/', views.UpdateChallengeFormView.as_view(), name='update'),
    path('<uuid:pk>/publish/', views.PublishView.as_view(), name='publish'),
    path('<uuid:pk>/pipeline/create/', views.CreatePipelineView.as_view(), name='pipeline-create'),
    path('<uuid:pk>/datasets/', include(('apps.challenge.challenge_dataset.urls', 'challenge_dataset'))),
    path('<uuid:pk>/submissions/', include(('apps.challenge.challenge_submission.urls', 'challenge_submission'))),
    path('<uuid:pk>/leaderboard/', include(('apps.challenge.challenge_leaderboard.urls', 'challenge_leaderboard'))),
    path('<uuid:pk>/evaluation-code/', views.EvaluationCodeView.as_view(), name='evaluation-code'),

]
