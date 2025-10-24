import os
import tempfile
from pathlib import Path

from django.conf import settings


def sign_csr(days, csr: Path | str):
    root_ca_crt = settings.CA_DIR / 'rootCA.crt'
    root_ca_key = settings.CA_DIR / 'rootCA.key'

    csr_path = csr
    if isinstance(csr, str):
        with tempfile.NamedTemporaryFile('w', delete=False) as f:
            csr_path = Path(f.name)
            f.write(csr)

    if not csr_path.exists():
        raise Exception(f'CSR not found at {csr}')

    if not root_ca_crt.exists() or not root_ca_key.exists():
        raise Exception(f'CA private key not found at {root_ca_key}')

    with tempfile.NamedTemporaryFile('w', delete=False) as f:
        crt = f.name

    cmd = f'openssl x509 -req -in {csr_path} -CA {root_ca_crt} -CAkey {root_ca_key} -CAcreateserial -out {crt} -days {days} -sha256'
    os.system(cmd)

    csr_path.unlink(missing_ok=True)

    with open(crt, 'r') as f:
        crt_str = f.read()

    os.unlink(crt)

    return crt_str


def create_private_key(output: Path):
    print(output)
    output = settings.CERTS_DIR / output
    output.parent.mkdir(exist_ok=True, parents=True)
    os.system(f'openssl genrsa -out {output} 4096')
    return output


def create_root_certificate(key, cert_output, common_name):
    cmd = f'openssl req -x509 -new -nodes -key {key} -sha256 -subj "/CN={common_name}/C=/ST=/L=/O=/OU=" -days 1024 -out {cert_output}'
    os.system(cmd)


def create_certificate_authority(key_output, cert_output, common_name):
    create_private_key(key_output)
    create_root_certificate(key_output, cert_output, common_name)


def create_csr(common_name, key, output: Path):
    output.parent.mkdir(parents=True, exist_ok=True)
    l = min(64, len(common_name))
    cmd = f'openssl req -new -key {key} -subj "/CN={common_name[:l]}/C=/ST=/L=/O=/OU=" -sha256 -out {output}'
    os.system(cmd)
