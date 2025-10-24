from django.conf import settings
from django.core.management.base import BaseCommand

from apps.user.user_profile.models import Profile


class Command(BaseCommand):
    help = "Generates a private key for a user."

    def add_arguments(self, parser):
        parser.add_argument('user_identifier', type=str, nargs='+')

    def handle(self, *args, **options):
        user_identifier = options['user_identifier'][0]

        profile = Profile.objects.get(identifier=user_identifier)
        if profile.has_private_key:
            print("User already has a private key.")
            return

        if profile.node.identifier != settings.IDENTIFIER:
            print("User is not from this node.")
            return

        profile.generate_private_key()
        print("Private key generated.")
