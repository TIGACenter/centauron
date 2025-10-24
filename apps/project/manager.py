from django.db.models import Q

from apps.core.managers import BaseManager
from apps.federation.federation_invitation.models import FederationInvitation


class ProjectManager(BaseManager):

    def for_user(self, user: 'Profile'):
        return self.filter(Q(created_by=user) | (Q(members__user=user) & Q(members__invite__status=FederationInvitation.Status.ACCEPTED))).distinct()

    def for_user_owner(self, user):
        return self.filter(created_by=user)
