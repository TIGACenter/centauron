from django.contrib.auth import get_user_model

from apps.core.managers import BaseManager

User = get_user_model()


class ProfileManager(BaseManager):

    def create_and_return(self, identifier: str):
        from apps.user.user_profile.models import Profile
        try:
            return self.get_by_identifier(identifier)
        except Profile.DoesNotExist:
            user, _ = User.objects.get_or_create(username=str(identifier))
            return self.create(identifier=identifier, user=user)
