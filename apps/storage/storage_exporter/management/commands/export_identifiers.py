import csv

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.storage.models import File


class Command(BaseCommand):
    help = "Exports all identifiers of an import folder."

    def add_arguments(self, parser):
        parser.add_argument('import_folder_name', nargs=1)

    def handle(self, *args, **options):
        files = File.objects.filter(import_folder__path__contains=options['import_folder_name'][0], imported=False)

        export_file = settings.STORAGE_EXPORT_DIR / f'identifier-{timezone.now().isoformat()}.csv'
        with export_file.open('w') as f:
            writer = csv.DictWriter(f, fieldnames=['id', 'name'], delimiter=';')
            writer.writeheader()
            for e in files:
                writer.writerow(dict(id=str(e.identifier), name=e.original_filename))

        self.stdout.write(f'Identifiers exported into {export_file}')
