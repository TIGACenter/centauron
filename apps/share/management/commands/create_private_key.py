from django.core.management.base import BaseCommand

from apps.federation import cert_utils


class Command(BaseCommand):
    help = 'Creates a new private key.'

    def add_arguments(self, parser):
        parser.add_argument('path', nargs='+', type=str)

    def handle(self, *args, **options):
        cert_utils.create_private_key(options['path'][0])
