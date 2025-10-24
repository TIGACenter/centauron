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
    help = "Deletes extra data with application identifier."

    def add_arguments(self, parser):
        parser.add_argument('application_identifier', nargs='+')

    def handle(self, *args, **options):
        ai = options['application_identifier'][0]
        count = ExtraData.objects.filter(application_identifier=ai).delete()
        logging.info(f'Deleted: {count}')
