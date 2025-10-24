import json
from functools import partial
from typing import Any, Dict

from django.db import models, transaction

from apps.federation.messages import MessageObject, CreateMessage
from apps.federation.models import Message
from apps.node.models import Node
from apps.user.user_profile.models import Profile


class OutboxMessage(Message):
    remote_location = models.URLField()

    def save(self, *args, **kwargs):
        self.box = Message.Box.OUTBOX
        return super(OutboxMessage, self).save(*args, **kwargs)

    @property
    def is_broadcast(self):
        return self.recipient is None

    @staticmethod
    def _build_message_header(message_object: MessageObject):
        pass

    @staticmethod
    def create(*, sender: Profile, recipient: Profile | None,
               message_object: MessageObject|str,
               message_type=CreateMessage,
               extra_data: Dict[str, Any] | None = None) -> 'OutboxMessage':
        if not isinstance(message_object, Dict):
            message_object.recipient = recipient.identifier if recipient is not None else None
            message_object.sender = sender.identifier

        message = message_type(object=message_object,
                               from_=sender.node.identifier,
                               to=recipient.node.identifier if recipient is not None else None)
        message= json.loads(message.model_dump_json(by_alias=True))
        return OutboxMessage.objects.create(sender=sender,
                                            recipient=recipient,
                                            message=message,
                                            extra_data=extra_data)

    def send(self, send_async=True):
        from apps.federation.outbox.tasks import send_outbox_message
        if send_async:
            transaction.on_commit(partial(send_outbox_message.delay, self.id_as_str))
        else:
            send_outbox_message(self.id_as_str)
