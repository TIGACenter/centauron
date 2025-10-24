from django.core.management.base import BaseCommand

from apps.storage.models import File
from apps.storage.storage_importer.tasks import run_file_importer


class Command(BaseCommand):
    help = "Deletes all files that origin from a user."

    def add_arguments(self, parser):
        parser.add_argument(
            'user_identifier',
            type=str,
            help='Identifier of the user.'
        )
    def handle(self, *args, **options):
        user_identifier = options['user_identifier']
        File.objects.filter(origin__identifier=user_identifier).delete()

