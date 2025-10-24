import logging

from celery import shared_task
import logging

from apps.federation.inbox.models import InboxMessage
from apps.federation.messages import Message


@shared_task
def process_inbox_message(message_id):
    persisted_message = InboxMessage.objects.get(pk=message_id)
    message = Message(**persisted_message.message)
    object = message.object
    model = id if isinstance(object, str) else object.type

    try:
        persisted_message.processing = True
        persisted_message.save(update_fields=['processing'])
        m, kwargs = InboxMessage.get_model(model)
        logging.info('Processing inbox message %s with %s', model, m)
        kwargs.update(dict(inbox_message=persisted_message, message=message))
        m(**kwargs)
        persisted_message.processed = True
        persisted_message.processing = False
        persisted_message.save(update_fields=['processed', 'processing'])
    except Exception as e:
        logging.exception(e)
        # TODO send a message with the exception


@shared_task
def process_inbox_messages():
    for message in InboxMessage.objects.filter(processed=False):
        process_inbox_message(message.id_as_str)

