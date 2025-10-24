import logging
import sys
from pathlib import Path

import httpx
from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Tests the connection to the DSF."

    def handle(self, *args, **options):
        url = settings.FHIR_SERVER
        cert = Path(settings.DSF_CERTIFICATE)
        private_key = Path(settings.DSF_CERTIFICATE_PRIVATE_KEY)

        logging.info(f'Connecting to: {url}')
        if not cert.exists():
            logging.error(f'Certificate does not exist at: {cert}')
            sys.exit(1)

        if not private_key.exists():
            logging.error(f'Private key does not exist at: {private_key}')
            sys.exit(1)

        response = httpx.get(url, headers={'Accept': 'application/json'}, cert=(str(cert), str(private_key)))

        if response.status_code != 405:
            logging.error(response.text)
            sys.exit()

        logging.info('Successfully connected to DSF.')
