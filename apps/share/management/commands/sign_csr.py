from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.sharing import cert_utils


class Command(BaseCommand):
    help = 'Signs a client certificate.'

    def add_arguments(self, parser):
        parser.add_argument('csr', type=str)
        parser.add_argument('days', nargs='?', default=365, type=int)

    def handle(self, *args, **options):
        days = options['days']
        csr = Path(options.get('csr'))

        self.stdout.write(f'Days: {days}')
        self.stdout.write(f'CSR: {csr}')

        try:
            crt = cert_utils.sign_csr(days, csr)
            with open(settings.CERTS_DIR / (csr.name[:-3] + 'crt'), 'w') as f:
                f.write(crt)
            self.stdout.write(
                self.style.SUCCESS(f'Certificate signed and saved at {crt.relative_to(settings.CERTS_DIR)}'))

        except Exception as e:
            self.stderr.write(e)
