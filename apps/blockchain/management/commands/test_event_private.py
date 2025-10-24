from django.conf import settings
from django.core.management.base import BaseCommand

# from apps.blockchain.messages import TestMessage, Actor, Object, Identifiable
from apps.federation.messages import TestMessage, TestObject, TestMessageContent
from apps.federation.outbox.models import OutboxMessage
from apps.user.user_profile.models import Profile


class Command(BaseCommand):
    help = "Logs a test event to the blockchain."

    def add_arguments(self, parser):
        parser.add_argument('to', nargs='+', type=str)
        parser.add_argument('from', nargs='*', type=str, default=None)

    def handle(self, *args, **options):
        d = {
            'identifier': settings.IDENTIFIER,
            'display': settings.NODE_NAME,
            'model': "node"
        }
        # id = Identifiable(**d)
        to_did = options['to'][0]

        if len(options['from']) == 1:
            from_did = options['from'][0].strip()
        else:
            from_did = settings.ORGANIZATION_DID

        print(f"From: {from_did}")
        print(f"To: {to_did}")

        # msg = TestMessage(actor=Actor(organization=settings.ORGANIZATION_DID, **d),
        #                            object=Object(model="node", value=id))
        obj = TestObject(content=TestMessageContent(model="node", value=d))
        om = OutboxMessage.create(
            sender=Profile.objects.get(identity=from_did),
            recipient=Profile.objects.get(identity=to_did),
            message_type=TestMessage,
            message_object=obj
        )
        om.send(send_async=False)
        # get_backend().send_message()
        #
        # send_private_message(topic=settings.FIREFLY_MESSAGE_TOPIC_DATA_TRANSFER,
        #                      data=msg.model_dump(),
        #                      recipient_dids=to_did,
        #                      send_async=False,
        #                      sender=from_did)
