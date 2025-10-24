import httpx
from constance import config
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from httpx import ConnectError
from rest_framework.authtoken.models import Token

from apps.federation.messages import UserMessage, UserMessageContent
from apps.federation.outbox.models import OutboxMessage
from apps.share.share_token import token_utils
from apps.utils import get_user_node

User = get_user_model()

class Command(BaseCommand):
    help = "Registers this node at the global Centauron Certificate Authority."

    # def add_arguments(self, parser):
    #     parser.add_argument('sample', nargs='+')

    def handle(self, *args, **options):
        data = UserMessage(content=UserMessageContent(identifier=settings.IDENTIFIER,
                                                      common_name=settings.COMMON_NAME,
                                                      did=settings.ORGANIZATION_DID,
                                                      address=settings.ADDRESS,
                                                      node_name=settings.NODE_NAME,
                                                      api_address=settings.API_ADDRESS,
                                                      cdn_address=settings.CDN_ADDRESS))
        token = token_utils.create_token('Node', f'Node {settings.IDENTIFIER}', data.dict())

        self.stdout.writelines(['Registering your node with the following data:',
                                f'identifier: {settings.IDENTIFIER}',
                                f'common_name: {settings.COMMON_NAME}',
                                f'did: {settings.ORGANIZATION_DID}',
                                f'cdn_address: {settings.CDN_ADDRESS}',
                                f'address: {settings.ADDRESS}',
                                f'api_address: {settings.API_ADDRESS}',
                                f'node_name: {settings.NODE_NAME}'])

        # create cca user locally
        user_cca, _ = User.objects.get_or_create(username=settings.CCA_LOCAL_USERNAME)
        auth_token, _ = Token.objects.get_or_create(user=user_cca)

        url = f'{settings.CCA_URL}nodes/register/'
        payload = {'token': token, 'auth_token': auth_token.key}
        try:
            response = httpx.post(url, json=payload)
        except ConnectError as e:
            user_cca.delete()
            self.stderr.write("Cannot reach Centauron Certificate Authority. Please try again later.")
            return


        if response.status_code != 200:
            self.stderr.write(
                'Registering your node did not complete successfully. Check your settings or is the node already registered?')
            return

        b = response.json()
        token = b['token']
        # store cca token
        config.CCA_TOKEN = token

        # FIXME actually the node should be announced by the CCA and not by the node itself.
        node_user = get_user_node()
        OutboxMessage.create(sender=node_user,
                             recipient=None,
                             message_object=data).send()


        self.stdout.write("Node registered successfully.", self.style.SUCCESS)
        self.stdout.write(f"Please add COMMON_NAME={b['common_name']} to your configuration.")
        self.stdout.write("Next: python manage.py obtain_certificate")
