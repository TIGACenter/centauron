from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.federation import cert_utils


class Command(BaseCommand):
    help = 'Creates a new certificate signing request.'

    def add_arguments(self, parser):
        parser.add_argument('common_name', nargs='+', type=str)
        parser.add_argument('key', nargs='+', type=str)
        parser.add_argument('output', nargs='+', type=str)

    def handle(self, *args, **options):
        key = options['key'][0]
        key = settings.CERTS_DIR / Path(key)
        output = settings.CERTS_DIR / options['output'][0]
        cert_utils.create_csr(common_name=options['common_name'][0],
                              key=key,
                              output=output)
