from django.urls import path

from apps.federation.federation_invitation.api import InvitationAPIView, InvitationUpdateView
from apps.federation.federation_invitation.views import SearchForCollaboratorView, QueryView, CreateInviteView, \
    InvitationListView, AcceptOrDeclineInvitationView

urlpatterns = [
    path('search/', SearchForCollaboratorView.as_view(), name='search'),
    path('query/', QueryView.as_view(), name='query'),
    path('create/', CreateInviteView.as_view(), name='create'),
    path('list/', InvitationListView.as_view(), name='list'),
    path('<uuid:pk>/accept_or_decline/', AcceptOrDeclineInvitationView.as_view(), name='accept-or-decline'),
    # # api views
    # TODO both endpoints are for match making via CA. investigate if they can be removed as this is now done via firefly
    path('receive/', InvitationAPIView.as_view()),
    path('update/', InvitationUpdateView.as_view()),
]
