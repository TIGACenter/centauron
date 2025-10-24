from django.core.management.base import BaseCommand

from apps.storage.storage_importer.tasks import run_file_importer


class Command(BaseCommand):
    help = "Runs the file importer."

    def handle(self, *args, **options):
        run_file_importer()
