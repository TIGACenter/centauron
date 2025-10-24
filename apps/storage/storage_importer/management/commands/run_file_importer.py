from django.core.management.base import BaseCommand
import logging

from apps.storage.storage_importer.tasks import run_file_importer


class Command(BaseCommand):
    help = "Runs the file importer."

    def handle(self, *args, **options):
        logging.info('Start running file importer.')
        run_file_importer()
        logging.info('File importe run.')
