import logging
from urllib.parse import unquote

from django.core.cache import cache
from django.http import HttpResponse, FileResponse
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.auth.auth_certificate.authentication import CertificateAuthentication, DownloadTokenAuthentication
from apps.blockchain.messages import ExportMessage, Object, DownloadMessage
from apps.blockchain.models import Log
from apps.core import identifier
from apps.federation.file_transfer.backends import get_file_serve_backend, BaseFileServeBackend
from apps.federation.file_transfer.models import DownloadToken
from apps.permission.models import Permission
from apps.storage.models import File
from apps.user.user_profile.models import Profile


class FileServeView(APIView):
    authentication_classes = [DownloadTokenAuthentication, CertificateAuthentication]
    permission_classes = [IsAuthenticated]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.backend: BaseFileServeBackend = get_file_serve_backend()()

    def log_to_blockchain(self, user, download_token: DownloadToken, file_identifier:str):
        if download_token is not None:
            download_token = DownloadToken.objects.get(token=download_token)

            # only log if it was not logged before or this will be done for each request by a download manager.
            # if the download manager downloads via byte ranges then one download will create like 100 logs.
            # set the cache for 24 hours so the user has 24 hours to download before a new log will be issued. this will be long enough hopefully
            cache_key = download_token.id_as_str
            if not cache.get(cache_key):
                cache.set(cache_key, True, timeout=86400)
                Log.send_broadcast(ExportMessage(actor=user.to_actor(), object=Object(model="file", value=[file_identifier]), context={'challenge': download_token.challenge.to_identifiable()}), send_async=True)
        else:
            # somehow add the challenge as well. if not this log does not say much
            Log.send_broadcast(DownloadMessage(actor=user.to_actor(), object=Object(model="file", value=[file_identifier])), send_async=True)

    def get(self, request, **kwargs):
        # TODO cache if the user is permitted to download a file and then serve the download directly to avoid a high server load
        file_identifier = request.GET.get('id', None)
        if file_identifier is None:
            logging.warning('No file identifier provided for download.')
            return HttpResponse(status=404)

        file_identifier = unquote(file_identifier)

        user = request.META.get('HTTP_X_USER', request.user.profile.identifier)
        node = request.auth
        logging.debug(f"Download request for node {node} and user {user}")

        user = Profile.objects.get(node=node, identifier=user)
        # check permissions for this user and file
        file_identifier = identifier.from_string(file_identifier)
        granted_permission = Permission.objects.has_permissions(user, file_identifier, Permission.Action.DOWNLOAD)
        if granted_permission == Permission.Permission.ALLOW:
            try:
                # TODO this must be imported to the user and not imported in general. or can we assume that download only takes place when downloading from a challenge and then the data is imported already? not sure
                file = File.objects.get_by_identifier(file_identifier, **{'imported': True})
                # msg = UseMessage(actor=cdef.created_by.to_actor(), object=Object(model="slide", value=files),
                #                  context={'submission': submission.to_identifiable(),
                #                           'challenge': submission.challenge.to_identifiable()})
                download_token = request.query_params.get('token', None)

            except File.DoesNotExist:
                logging.warning('File does not exist.')
                return HttpResponse(status=404)

            try:
                file_handle = self.backend.get_file(file_identifier)
            except Exception as e:
                logging.error('File handle not found for:')
                logging.error(e)
                return HttpResponse(status=404)

            # according to http specs whitespace needs to be escaped https://www.rfc-editor.org/rfc/rfc2616#section-2.2
            file_name = file.name.replace(' ', '\ ')



            if 'Range' not in request.headers:
                self.log_to_blockchain(user, download_token, file_identifier)
                return FileResponse(file_handle,
                                    as_attachment=True,
                                    filename=file_name)
            else:
                file_size = self.backend.get_file_size(file_identifier)
                range_header = request.headers['Range']
                start, end = range_header.split('=')[1].split('-')
                start = int(start.strip())
                end = int(end.strip()) if end else file_size - 1

                logging.info(f'Range {start} - {end} requested for file {file_identifier}.')


                # Validate the range
                if start >= file_size or end >= file_size or start > end:
                    return HttpResponse("Requested range not satisfiable", status=416)
                # Open the file and seek to the requested position
                file_handle.seek(start)
                content = file_handle.read(end - start + 1)

                # Create the response
                response = HttpResponse(content, status=206)
                response['Content-Type'] = 'application/octet-stream'
                response['Content-Length'] = str(len(content))
                response['Content-Range'] = f'bytes {start}-{end}/{file_size}'
                response["Content-Disposition"] = f"attachment; filename=\"{file_name}\""
                self.log_to_blockchain(user, download_token, file_identifier)
                return response
        return HttpResponse(status=403)
