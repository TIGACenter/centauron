from django.core.management.base import BaseCommand
from django.conf import settings
from pathlib import Path

from apps.storage.models import File


class Command(BaseCommand):
    help = "Deletes all files that are not referenced anymore in the database."

    def add_arguments(self, parser):
        parser.add_argument(
            '--go',
            action='store_true',
            help='If set,files are actually deleted.',
            default=False,
        )

    def handle(self, *args, **options):
        files = Path(settings.STORAGE_DATA_DIR)
        is_go_run = options.get('go', False)
        i = 0
        for file in files.iterdir():
            if file.is_file():
                if not File.objects.filter(path=file.name).exists():
                    i += 1
                    if not is_go_run:
                        self.stdout.write(f"[dry] Deleting file [{file.name}]")
                    else:
                        self.stdout.write(f"Deleting file [{file.name}]")
                        file.unlink()

        self.stdout.write(self.style.SUCCESS(f"Deleted {i} files."))
