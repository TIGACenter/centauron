from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from apps.federation.messages import UserMessage, UserMessageContent
from apps.federation.outbox.models import OutboxMessage
from apps.utils import get_user_node

User = get_user_model()


class Command(BaseCommand):
    help = "Announces a node to the network."

    def handle(self, *args, **options):
        data = UserMessage(content=UserMessageContent(identifier=settings.IDENTIFIER,
                                                      common_name=settings.COMMON_NAME,
                                                      did=settings.ORGANIZATION_DID,
                                                      address=settings.ADDRESS,
                                                      node_name=settings.NODE_NAME,
                                                      api_address=settings.API_ADDRESS,
                                                      cdn_address=settings.CDN_ADDRESS))

        self.stdout.writelines(['Registering your node with the following data:',
                                f'identifier: {settings.IDENTIFIER}',
                                f'common_name: {settings.COMMON_NAME}',
                                f'did: {settings.ORGANIZATION_DID}',
                                f'cdn_address: {settings.CDN_ADDRESS}',
                                f'address: {settings.ADDRESS}',
                                f'api_address: {settings.API_ADDRESS}',
                                f'node_name: {settings.NODE_NAME}'])

        # FIXME actually the node should be announced by the CCA and not by the node itself.
        node_user = get_user_node()
        OutboxMessage.create(sender=node_user,
                             recipient=None,
                             message_object=data).send()

        self.stdout.write("Node announced successfully.", self.style.SUCCESS)
