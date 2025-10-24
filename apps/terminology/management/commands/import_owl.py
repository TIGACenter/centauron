import csv
import io
import uuid

import owlready2
import pandas
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
import logging

from apps.core import db_utils
from apps.terminology.models import CodeSystem, Code


class Command(BaseCommand):
    help = "Imports an owl file from a url."

    def add_arguments(self, parser):
        parser.add_argument('url', nargs='+')

    def handle(self, *args, **options):
        url = options['url'][0]
        logging.info(f'Importing ontology from {url}. This can take a while.')
        onto = owlready2.get_ontology(url)
        onto.load()
        logging.info(f'Ontology loaded.')

        with io.StringIO() as buffer:
            csv_header = ['id', 'date_created', 'last_modified', 'code', 'human_readable', 'codesystem_name', 'codesystem_id']
            now = timezone.now().isoformat()
            writer = csv.writer(buffer)
            writer.writerow(csv_header)
            cs = CodeSystem(name=url, uri=onto.base_iri)
            cs_id = cs.id_as_str
            for t in onto.get_namespace(url).classes():
                label = t.label[0] if len(t.label) > 0 else ''
                # print(t.name, ' --> ', label)
                writer.writerow([str(uuid.uuid4()), now, now, t.name, label, cs.name, cs_id])
            with transaction.atomic():
                cs.save()
                buffer.seek(0)
                df = pandas.read_csv(buffer)
                logging.info('Importing %s classes.', len(df.index))
                db_utils.insert_with_copy_from_and_tmp_table(df, Code.objects.model._meta.db_table)
                logging.debug('Committing transaction.')
            logging.info('Done.')

