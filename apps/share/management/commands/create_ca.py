import os

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.sharing import cert_utils


class Command(BaseCommand):
    help = 'Creates a new certificate authority.'

    def add_arguments(self, parser):
        parser.add_argument('common_name', nargs='+', type=str)

    def handle(self, *args, **options):
        # create root key
        key_path = settings.CERTS_DIR / 'ca'
        key_path.mkdir(exist_ok=True, parents=True)
        key_path /= 'rootCA.key'
        os.system(f'openssl genrsa -out {key_path} 4096')

        # openssl req -x509 -new -nodes -key rootCA.key -sha256 -days 1024 -out rootCA.crt
        self.stdout.write("Creating your server certificate.")
        crt_path = settings.CERTS_DIR / 'ca' / 'rootCA.crt'
        cert_utils.create_certificate_authority(key_path, crt_path, options['common_name'])

        self.stdout.write(
            self.style.SUCCESS('Successfully created your private key at "%s"' % key_path))
        self.stdout.write(self.style.SUCCESS(
            'Successfully created your server certificate at "%s"' % crt_path))
