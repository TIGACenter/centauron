from django.core.management.base import BaseCommand

from apps.federation.file_transfer.tasks import watch_download_state


class Command(BaseCommand):
    help = "Watches the download state of aria2 downloads.."

    def handle(self, *args, **options):
        watch_download_state()
