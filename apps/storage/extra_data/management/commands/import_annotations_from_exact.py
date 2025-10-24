import json
import logging

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from tqdm import tqdm

from apps.core import identifier
from apps.storage.extra_data.models import ExtraData
from apps.storage.models import File
from apps.terminology.models import Code
from apps.user.user_profile.models import Profile
from apps.utils import get_user_node

User = get_user_model()


class Command(BaseCommand):
    help = "Imports annotations done in exact."

    def add_arguments(self, parser):
        parser.add_argument('file', nargs='+')
        parser.add_argument('--term', action="append",
                            help='Term mapping. Must be in format "source_term=codesystem#term".')

    def handle(self, *args, **options):
        annotations = self.process_exact_anno_export(options['file'][0])
        application_identifier = 'io.centauron.annotation'

        term_mapping = {}
        if 'term' in options:
            for t in options['term']:
                if '=' not in t:
                    logging.warning('Ignoring term mapping %s due to wrong format.', t)
                    continue
                k, v = t.split('=')
                if '#' not in v:
                    logging.warning('Ignoring term mapping %s due to wrong format.', t)
                    continue

                cs, code = v.strip().split('#')
                try:
                    term_mapping[k.strip()] = Code.objects.get_by_code_and_codesystem(code, cs)
                except Code.DoesNotExist:
                    logging.warning('Code %s does not exist in codesystem %s.', code, cs)
                    continue

        logging.info('Term mapping: %s', term_mapping)

        for a in tqdm(annotations):
            slide = a['slide']
            id = a['id']
            author = a['author']  # the username
            type = a['type']
            coordinates = a['coordinates']
            if type in term_mapping:
                term = term_mapping[type].human_readable
            else:
                term = None

            try:
                user = Profile.objects.get(user__username=author)
            except Profile.DoesNotExist:
                user = get_user_node()
                logging.error('User %s not found. Selecting user "node" instead.', author)

            try:
                file = File.objects.get(name=slide)
            except File.DoesNotExist:
                logging.error('File %s not found. Skipping annotation.', slide)
                continue

            # TODO check if this is as expected by the annotation backend.
            data = {'id': id, 'data': coordinates, 'label': term}
            qs = ExtraData.objects.filter(file=file, application_identifier=application_identifier, data__id=id)
            if qs.exists():
                ed = qs.first()
                ed.data = data
                ed.save(update_fields=['data'])
                logging.info('Annotation updated.')
            else:
                ExtraData.objects.create(
                    origin=get_user_node(),
                    created_by=user,
                    file=file,
                    application_identifier=application_identifier,
                    data=data,
                    identifier=identifier.create_random('extra-data'))
                logging.info('Annotation created.')

        logging.info('Done importing annotations.')

    # from felipe
    def process_exact_anno_export(self, anno_file_path):
        with open(anno_file_path, "r") as f:
            for n, i in enumerate(f.readlines()):
                try:
                    yield json.loads(i.replace("\n", "").replace("],]", "]]"))
                except:
                    continue
