import logging

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.blockchain.messages import TestMessage, Actor, Object, Identifiable
from apps.blockchain.models import Log


class Command(BaseCommand):
    help = "Logs a test event to the blockchain."

    def handle(self, *args, **options):
        d = {
            'identifier': settings.IDENTIFIER,
            'display': settings.NODE_NAME,
            'model': "node"
        }
        id = Identifiable(**d)
        Log.send_broadcast(TestMessage(
            actor=Actor(
                organization=settings.ORGANIZATION_DID,
                **d
            ),
            object=Object(model="node", value=id)
        ))
