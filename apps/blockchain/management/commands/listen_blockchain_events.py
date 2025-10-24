from django.core.management.base import BaseCommand

from apps.blockchain.backends import get_adapter


class Command(BaseCommand):
    help = "Starts the websocket client, listens and processes events from the blockchain."

    def handle(self, *args, **options):
        # run_client()
        a = get_adapter()()
        a.start()

