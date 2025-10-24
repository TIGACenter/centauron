from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from apps.user.user_profile.models import Profile

User = get_user_model()

class Command(BaseCommand):
    help = "Deletes a user the local node. If the user is published and stemming from the local node, the user is also deleted from the CCA."

    def add_arguments(self, parser):
        parser.add_argument('username', nargs='+')

    def handle(self, *args, **options):
        username = options['username'][0]
        user = User.objects.get(username=username)
        user.delete()

        # TODO delete user from CCA if user is stemming from local node.
        # TODO delete user from keycloak if local user
