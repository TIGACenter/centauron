from django.conf import settings
from django.core.management.base import BaseCommand

from apps.user.user_profile.models import Profile


class Command(BaseCommand):
    help = "Migrates all existing users on this node and generates private keys for them."

    def handle(self, *args, **options):
        qs = Profile.objects.filter(node__identifier=settings.IDENTIFIER)
        for profile in qs:
            print("Migrating private key for profile {}".format(profile.identity))
            if profile.has_private_key:
                print("User already has a private key.")
                return

            if profile.node.identifier != settings.IDENTIFIER:
                print("User is not from this node.")
                return

            profile.generate_private_key()
            print("Private key generated.")
