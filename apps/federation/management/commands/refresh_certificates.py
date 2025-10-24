import logging

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.federation.federation_invitation import cca_utils
from apps.node.models import Node


class Command(BaseCommand):
    help = "Sends request to the Centauron Certificate Authority to refresh the certificate fingerprints."

    def handle(self, *args, **options):
        url = f'{settings.CCA_URL}certificates/get/'

        for node in Node.objects.exclude(identifier=settings.IDENTIFIER):
            payload = dict(identifier=node.identifier)
            try:
                response = cca_utils.post(url, payload)
            except Exception as e:
                self.stderr.write("Cannot reach Centauron Certificate Authority. Please try again later. %s", str(e))
                return

            if response.status_code != 200:
                self.stderr.write('CAA responded with an error code. Try again.')
                return

            data = response.json()
            tb = data['thumbprint']
            try:
                fhirserver = data.get('fhirserver')
                if fhirserver is not None:
                    node.address_fhir_server = fhirserver
                # node.update_resource_on_fhir_server(tb)
            except Exception as e:
                # presumable the Organization resource does not exist on the server.
                # try and create it here
                logging.exception(e)

        self.stdout.write('Done.')
