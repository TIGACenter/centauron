from django.core.management.base import BaseCommand
import logging

from apps.storage.storage_importer.models import ImportFolder
from apps.study_management.models import Study


class Command(BaseCommand):
    help = "Creates an import folder for a study."

    def add_arguments(self, parser):
        parser.add_argument('study_id', nargs='+')

    def handle(self, *args, **options):
        study = Study.objects.get(pk=options.get('study_id')[0])
        f = ImportFolder.objects.create_for_study(study)

        logging.info('ImportFolder created for study %s at %s.',  study.name, f.path)
