import csv

from django.contrib.staticfiles import finders
from django.core.management.base import BaseCommand
from django.db import transaction, ProgrammingError

from apps.terminology.models import CodeSystem, Code


class Command(BaseCommand):
    help = "Imports the CENTAURON stainings."

    def handle(self, *args, **options):
        try:
            CodeSystem.objects.all()
        except ProgrammingError as e:
            self.stderr.write('Cannot get code systems. Did you run `python manage.py migrate`?')
            self.stderr.write(str(e))
            return

        centauron_stainings_csv = finders.find('codesystems/centauron-stainings.csv')
        if centauron_stainings_csv is None:
            self.stderr.write('CENTAURON stainings not found.')
            return

        codesystem_uri = 'http://centauron.net/stainings'
        codesystem_name = 'CENTAURON stainings'
        code_system, created = CodeSystem.objects.get_or_create(name=codesystem_name, uri=codesystem_uri)
        if created:
            self.stdout.write(f'CodeSystem created.')
        else:
            self.stdout.write(f'CodeSystem already exists.')

        created_counter = 0
        with open(centauron_stainings_csv) as f, transaction.atomic():
            reader = csv.DictReader(f)
            for row in reader:
                name = row['name']
                human_readable = row['name']
                code, created = Code.objects.get_or_create(code=name,
                                                           human_readable=human_readable,
                                                           codesystem=code_system,
                                                           codesystem_name=codesystem_name)
                if created:
                    created_counter += 1
        self.stdout.write(f'Codes created: {created_counter}')
