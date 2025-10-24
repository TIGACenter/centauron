from django.core.management.base import BaseCommand
from django.db import transaction
from lxml import etree

from apps.terminology.models import Code, CodeSystem

# the german version of ICD-O-3 can be downloaded here: https://www.bfarm.de/DE/Kodiersysteme/Services/Downloads/_node.html
# direct link (not clear if always working):
# download link: https://multimedia.gsb.bund.de/BfArM/downloads/klassifikationen/icd-o-3/revision2019/icdo3rev2-2019syst-claml-20210129.zip
class Command(BaseCommand):
    help = "Imports the ICD-O-3."

    def add_arguments(self, parser):
        parser.add_argument('file', nargs='+')

    def handle(self, *args, **options):
        file = options.get('file')
        if file is None:
            self.stderr.write(f'File {file} not found. Please provide the full path (available in docker?)')
            return
        file = file[0]
        codesystem_uri = 'http://who.int/icd-o-3'
        ns = { 'u': codesystem_uri }
        with open(file, 'rb') as f:
            tree = etree.parse(f)
            codesystem_name = 'ICD-O-3'
            code_system, created = CodeSystem.objects.get_or_create(name=codesystem_name, uri=codesystem_uri)
            if created:
                self.stdout.write(f'CodeSystem created.')
            else:
                self.stdout.write(f'CodeSystem already exists.')

            root = tree.getroot()
            # all or nothing
            created_counter = 0
            with transaction.atomic():
                for entry in root.xpath('//Class[@kind="category"]'):
                    name = entry.attrib['code']
                    human_readable = entry.xpath('./Rubric[@kind="preferred"]/Label/text()')[0]
                    code, created = Code.objects.get_or_create(code=name,
                                               human_readable=human_readable,
                                               codesystem=code_system,
                                               codesystem_name=codesystem_name)
                    if created:
                        created_counter += 1
        self.stdout.write(f'Codes created: {created_counter}')
