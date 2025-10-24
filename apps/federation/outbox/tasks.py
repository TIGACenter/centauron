import logging

from apps.federation.outbox.backends import get_backend, LocalBackend, get_broadcast_backend
from apps.federation.outbox.models import OutboxMessage
from config import celery_app


@celery_app.task
def process_outbox_messages():
    for message in OutboxMessage.objects.filter(processed=False):
        send_outbox_message.delay(message.id_as_str)


@celery_app.task(bind=True)
def send_outbox_message(self, outboxmessage_pk):
    message = OutboxMessage.objects.get(pk=outboxmessage_pk)

    if message.processed:
        logging.warning('Message %s already processed.', message.pk)
        return

    # if the receiving and sending node are the same, take a shortcut and do not use any external component to send the message.
    if not message.is_broadcast and message.sender.node_id == message.recipient.node_id:
        LocalBackend().send_message(message)
    else:
        if message.is_broadcast:
            return get_broadcast_backend().send_message(message)
        else:
            return get_backend().send_message(message)
