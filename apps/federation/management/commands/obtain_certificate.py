import httpx
from constance import config
from cryptography import x509
from cryptography.hazmat.primitives import serialization
from django.conf import settings
from django.core.management.base import BaseCommand
from httpx import ConnectError

from apps.federation.cert_utils import create_private_key, create_csr


class Command(BaseCommand):
    help = "Creates a CSR and send it to the Centauron Certificate Authority."

    def handle(self, *args, **options):
        key_path = settings.CERTS_DIR / 'private_key.pem'
        key = create_private_key(key_path)
        output = settings.CERTS_DIR / "csr.pem"

        if settings.COMMON_NAME is None:
            self.stderr.write("COMMON_NAME is not set.")
            return

        create_csr(common_name=settings.COMMON_NAME, key=key, output=output)

        with output.open() as f:
            csr = f.read()

        url = f'{settings.CCA_URL}certificates/issue/'
        payload = dict(csr=csr)
        try:
            response = httpx.post(url, timeout=30, json=payload, headers={'Authorization': f'Token {config.CCA_TOKEN}'})
        except Exception as e:
            self.stderr.write("Cannot reach Centauron Certificate Authority. Please try again later. %s", str(e))
            return

        if response.status_code != 200:
            self.stderr.write('CAA responded with an error code. Try again.')
            return

        response_data = response.json()
        certificate = response_data['certificate']
        certificate_path = settings.CERTS_DIR / 'certificate.pem'
        with certificate_path.open('w') as f:
            f.write(certificate)

        with certificate_path.open('rb') as f:
            cert = x509.load_pem_x509_certificates(f.read())

        with (settings.CERTS_DIR / 'chain.pem').open('wb') as f:
            for i in range(1, len(cert)):
                f.write(cert[i].public_bytes(serialization.Encoding.PEM))

        # delete csr
        output.unlink()

        config.CERTIFICATE_THUMBPRINT = response_data['thumbprint']
        self.stdout.write(f'CERTIFICATE_THUMBPRINT={config.CERTIFICATE_THUMBPRINT}')
        self.stdout.write('Certificate received.', self.style.SUCCESS)

        # on DSF startup the local organization is created as a FHIR organization resource.
