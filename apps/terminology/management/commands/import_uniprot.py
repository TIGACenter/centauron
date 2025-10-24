import gzip

from django.core.management.base import BaseCommand
from django.db import transaction
from lxml import etree

from apps.terminology.models import Code, CodeSystem

# download link: https://ftp.uniprot.org/pub/databases/uniprot/current_release/knowledgebase/taxonomic_divisions/uniprot_sprot_human.xml.gz

class Command(BaseCommand):
    help = "Imports the uniprot 'uniprot_sprot_human.xml.gz'."

    def add_arguments(self, parser):
        parser.add_argument('file', nargs='+')

    def handle(self, *args, **options):
        file = options.get('file')
        if file is None:
            self.stderr.write(f'File {file} not found. Please provide the full path (available in docker?)')
            return
        file = file[0]
        codesystem_uri = 'http://uniprot.org/uniprot'
        ns = { 'u': codesystem_uri }
        with gzip.open(file, 'rb') as f:
            tree = etree.parse(f)
            codesystem_name = 'Uniprot'

            qs = CodeSystem.objects.filter(uri=codesystem_uri)
            if qs.exists():
                code_system = qs.first()
                self.stdout.write(f'CodeSystem already exists.')
            else:
                code_system = CodeSystem.objects.create(uri=codesystem_uri, name=codesystem_name)
                self.stdout.write(f'CodeSystem created.')

            root = tree.getroot()
            # all or nothing
            created_counter = 0
            with transaction.atomic():
                for entry in root.xpath('//u:entry', namespaces=ns):
                    name = entry.xpath('./u:name/text()', namespaces=ns)[0]
                    recommended_names = entry.xpath('./u:protein/u:recommendedName/u:shortName/text() | ./u:protein/u:recommendedName/u:fullName/text()', namespaces=ns)
                    alternative_names = entry.xpath('./u:protein/u:alternativeName/u:shortName/text() | ./u:protein/u:alternativeName/u:fullName/text()', namespaces=ns)
                    # print(f'{name=}')
                    # print(f'{recommended_names=}')
                    # print(f'{alternative_names=}')

                    human_readable = recommended_names[0] if len(recommended_names) > 0 else name
                    code, created = Code.objects.get_or_create(code=name,
                                               human_readable=human_readable,
                                               codesystem=code_system,
                                               codesystem_name=codesystem_name)
                    if created:
                        created_counter += 1
        self.stdout.write(f'Codes created: {created_counter}')
