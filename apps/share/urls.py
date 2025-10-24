from django.urls import path, include

from apps.share import views

urlpatterns = [
    path('token/', include(('apps.share.share_token.urls', 'share_token'))),
    path('create', views.CreateShareDialogView.as_view(), name='create'),

]
