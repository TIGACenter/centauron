from django.conf import settings
from django.core.management.base import BaseCommand

from apps.blockchain.models import LastSeenBlock
from apps.user.user_profile.models import Profile


class Command(BaseCommand):
    help = "Sets the last seen block."

    def add_arguments(self, parser):
        parser.add_argument('block', type=int, nargs='*')

    def handle(self, *args, **options):
        block = options['block']
        if len(block) == 0:
            block = 0
        else:
            block = block[0]

        LastSeenBlock.objects.update(block=block)
