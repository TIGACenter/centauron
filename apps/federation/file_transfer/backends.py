import json
import logging
from importlib import import_module
from urllib.parse import quote

import requests
from django.conf import settings

from apps.core import identifier
from apps.federation.file_transfer.models import TransferItem
from apps.storage.models import File

FILE_SERVE_BACKEND = getattr(settings, 'FILE_SERVE_BACKEND',
                             'apps.federation.file_transfer.backends.PlainFileServeBackend')


def get_file_serve_backend():
    # grab the classname off of the backend string
    package, klass = FILE_SERVE_BACKEND.rsplit('.', 1)
    # dynamically import the module, in this case app.backends.adapter_a
    module = import_module(package)
    # pull the class off the module and return
    return getattr(module, klass)


class BaseFileServeBackend:

    def __init__(self):
        pass
        # self.backend = self.get_backend()

    # def get_backend(self):
    #     raise NotImplementedError()

    def get_file(self, identifier_str: str, **kwargs):
        raise NotImplementedError()

    def get_file_size(self, identifier_str: str, **kwargs):
        raise NotImplementedError()


class PlainFileServeBackend(BaseFileServeBackend):

    # def get_backend(self):
    def get_file(self, identifier_str: str, **kwargs):
        file = File.objects.get_by_identifier(identifier.from_string(identifier_str))
        return open(settings.STORAGE_DATA_DIR / file.path, 'rb')

    def get_file_size(self, identifier_str: str, **kwargs):
        return (settings.STORAGE_DATA_DIR / File.objects.get_by_identifier(
            identifier.from_string(identifier_str)).path).stat().st_size


# possible other implementations: a compressed file serve backend or an encoder / decoder file serve backend.


FILE_DOWNLOAD_BACKEND = getattr(settings, 'FILE_DOWNLOAD_BACKEND',
                                'apps.federation.file_transfer.backends.Aria2DownloaderBackend')


def get_file_download_backend():
    # grab the classname off of the backend string
    package, klass = FILE_DOWNLOAD_BACKEND.rsplit('.', 1)

    # dynamically import the module, in this case app.backends.adapter_a
    module = import_module(package)

    # pull the class off the module and return
    return getattr(module, klass)


class BaseFileDownloadBackend:
    def download_file(self, transfer_item: TransferItem):
        pass


class Aria2DownloaderBackend(BaseFileDownloadBackend):

    # def __init__(self, **kwargs):
    #     self.cert_file = Path(settings.DSF_CERTIFICATE)
    #     self.cert_key = Path(settings.DSF_CERTIFICATE_PRIVATE_KEY)

    def download_file(self, transfer_item: TransferItem):
        origin = transfer_item.file.origin
        origin_via = transfer_item.file.origin_via
        if origin_via is not None:
            origin = origin_via

        url = origin.node.cdn_address + f'?id={quote(transfer_item.file.identifier)}'
        logging.info('Start downloading file @ %s', url)

        # TODO can this all be done via firefly and ipfs??

        # TODO maybe load cert file and key only once in constructor to avoid some overhead on every call
        # TODO for dev the dev credentials are sent as an http header. Test if certificate auth is actually working with aria2 per "uri download request"
        # TODO if it is not working: consider using one time auth tokens for downloading or starting an aria2 server for each download session and provide certificate and private key aria2c --private-key ... <url>.

        dir = '/downloads'
        if transfer_item.download_folder is not None and len(transfer_item.download_folder.strip()) > 0:
            dir += f'/{transfer_item.download_folder}'
        opts = {'dir': dir, 'out': transfer_item.file.name, 'header': []}

        if settings.DOWNLOADER_DEBUG:
            c = settings.MY_DEV_CREDENTIALS
            opts['header'].append(f'X-FORWARDED-TLS-CLIENT-CERT-INFO: {c["X-FORWARDED-TLS-CLIENT-CERT-INFO"]}')
        # TODO this is a pretty shitty and insecure solution but the client certificate auth is not going to work
        # TODO here as this is only authenticating a node and not a user anymore...

        # add header X-USER=user_identifier so the correct user can be identified on the target side.
        opts['header'].append(f'X-USER: {transfer_item.created_by.identifier}')
        if settings.DOWNLOADER_CERTIFICATE is not None and settings.DOWNLOADER_CERTIFICATE_PRIVATE_KEY is not None:
            opts['certificate'] = str(settings.DOWNLOADER_CERTIFICATE)
            opts['private-key'] = str(settings.DOWNLOADER_CERTIFICATE_PRIVATE_KEY)

        jsonreq = json.dumps({'jsonrpc': '2.0', 'id': 'qwer',
                              'method': 'aria2.addUri',
                              'params': [f'token:{settings.DOWNLOADER_SECRET}', [url], opts]})
        response = requests.post(settings.DOWNLOADER_ADDRESS, jsonreq)
        if response.status_code == 200:
            gid = response.json()['result']
            transfer_item.download_gid = gid
            transfer_item.status = TransferItem.Status.CREATED
        else:
            transfer_item.error_message = str(response.status_code) + response.text
            transfer_item.status = TransferItem.Status.ERROR

        transfer_item.save()
