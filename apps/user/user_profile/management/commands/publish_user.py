from django.core.management.base import BaseCommand

from apps.user.user_profile.models import Profile


class Command(BaseCommand):
    help = "Publishes a user to the global user registry."

    def add_arguments(self, parser):
        parser.add_argument('identifier', nargs='+')

    def handle(self, *args, **options):
        user_identifier = options['identifier'][0]
        profile = Profile.objects.get(identifier=user_identifier)
        profile.publish_in_registry()
