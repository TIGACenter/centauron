import logging
from urllib.parse import unquote

from rest_framework import authentication, exceptions

from apps.federation.file_transfer.models import DownloadToken
from apps.node.models import Node
from apps.utils import get_user_node


def get_cn_from_str(s: str) -> str:
    cns = unquote(s)
    cns = cns.replace('%40', '@')
    # decoded_string = urllib.parse.unquote(encoded_string)
    # return cns.split(",")[0].split("=")[1]
    b = cns.split(",")[0].split("=")[2]
    return b[:-1]
    # print(decoded_string.split(",")[0].split("=")[1])
    # ls = cns.split(',')
    # l = ls[0]
    # pattern = r'(\"CN=(\w.*)\",{0,1})'
    # cn = re.findall(pattern, l)
    # return cn[0][1]


# Subject%3D%22CN%3Dfhir.ak.dev.centauron.net%40ca.centauron.io%22%2CSubject%3D%22CN%3D%22CENTAURON+CA%22+Intermediate+CA%22%2CSubject%3D%22CN%3D%22CENTAURON+CA%22+Root+CA%22


class DownloadTokenAuthentication(authentication.BaseAuthentication):

    def authenticate(self, request):
        query_token = request.GET.get('token')
        if query_token is None:
            return None
        try:
            token = DownloadToken.objects.get(token=query_token)
        except DownloadToken.DoesNotExist:
            raise exceptions.AuthenticationFailed()

        return (token.for_user.user, token.for_user.node)


class CertificateAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):
        cn = request.META.get('HTTP_X_FORWARDED_TLS_CLIENT_CERT_INFO', None)
        if cn is None:
            return None
        try:
            cn = get_cn_from_str(cn)
            logging.debug('Extracted common name: ' + str(cn))
            n = Node.objects.get(common_name=cn)
        except Node.DoesNotExist:
            logging.error('No node for with cn=[%s]', cn)
            raise exceptions.AuthenticationFailed(f'no user found for common name {cn}')

        # TODO return the user for this node
        return (get_user_node().user, n)  # node is accessible @ request.auth
