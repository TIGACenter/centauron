from django.db import models

from apps.core.models import Base


class Message(Base):
    class Meta:
        abstract = True

    class Box(models.TextChoices):
        INBOX = 'inbox'
        OUTBOX = 'outbox'

    # objects = MessageManager()

    message = models.JSONField(default=dict)
    response_body = models.TextField(default=None, null=True, blank=True)
    # if recipient is null, the message is a broadcast message
    recipient = models.ForeignKey('user_profile.Profile', on_delete=models.CASCADE,
                                  related_name='%(class)s_received_messages',
                                  null=True, blank=True)

    sender = models.ForeignKey('user_profile.Profile', on_delete=models.CASCADE, related_name='%(class)s_sent_messages')
    box = models.CharField(choices=Box.choices, default=Box.INBOX, max_length=10, editable=False)
    processed = models.BooleanField(default=False)
    processing = models.BooleanField(default=False)
    tries = models.IntegerField(default=0)
    status_code = models.IntegerField(default=None, blank=True, null=True)
    error = models.TextField(null=True, blank=True, default=None)
    # any extra data that could be necessary for sending e.g. data for DSF.
    extra_data = models.JSONField(blank=True, default=None, null=True)

    @property
    def get_object(self):
        return self.message['object']
