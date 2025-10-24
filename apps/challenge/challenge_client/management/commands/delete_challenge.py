from django.core.management.base import BaseCommand

from apps.challenge.models import Challenge


class Command(BaseCommand):
    help = "Deletes a challenge along with its submissions and everything."

    def add_arguments(self, parser):
        parser.add_argument('challenge_id', nargs='+')

    def handle(self, *args, **options):
        challenge_id = options['challenge_id'][0]
        r = Challenge.objects.get(pk=challenge_id).delete()
        print(r)
