import datetime
import json
import logging

from django.conf import settings
from django.db import models

from apps.blockchain.messages import Message
from apps.blockchain.tasks import send_broadcast_message_wrapper
from apps.core.models import Base


class Log(Base):
    event_date = models.DateTimeField()
    actor = models.ForeignKey('user_profile.Profile',
                              null=True, blank=True,
                              on_delete=models.CASCADE, related_name='log_entries')
    actor_identifier = models.CharField(max_length=255, blank=True)
    actor_display = models.CharField(max_length=255, null=True, blank=True)
    object = models.JSONField(blank=True)
    context = models.JSONField(blank=True, null=True)
    action = models.CharField(max_length=255)
    raw_message = models.JSONField(blank=True)
    raw_event = models.JSONField(blank=True)
    event_id = models.CharField(max_length=255)
    message_id = models.CharField(max_length=255)
    block_number = models.BigIntegerField()

    # project = models.ForeignKey('project.Project', null=True, blank=True, on_delete=models.CASCADE, related_name='logs')

    @property
    def event_as_json_string(self) -> str:
        return json.dumps(self.raw_event)

    @property
    def message_as_json_string(self) -> str:
        return json.dumps(self.raw_message)


    def to_human_readable(self):
        try:
            words = []
            if self.action == 'create':
                words.append('created')

            if self.action == 'add':
                words.append("added")

            model = self.object.get('model')
            value = self.object.get('value')
            if model == 'project':
                words.append("project")
                words.append(self.object['value']['display'])

            if model == 'user':
                return f'User {self.object["value"]["display"]} joined the network.'

            if model == 'submission' and self.action == 'submission-sent':
                words.append(f'sent submission {self.object["value"]["name"]} to challenge {self.context["challenge"]["display"]}')

            if model == 'slide':
                if self.action == 'create':
                    words[0] = 'added'
                    words.append(f'{len(value)}')
                    words.append(f"slides to project {self.context['project']['display']}")
                if self.action == "add":
                    words.append(f'{len(value)}')
                    words.append(
                        f"slides to dataset {self.context['dataset']['display']} in challenge {self.context['challenge']['display']}")

                if self.action == "use":
                    words.append(
                        f"used {len(value)} slides to run submission {self.context['submission']['display']} in challenge {self.context['challenge']['display']}")


            if model == "challenge":
                words.append("challenge")
                words.append(self.object['value']['display'])

            if model == "dataset":
                words.append("dataset")
                words.append(self.object['value']['display'])
                words.append(f"in challenge {self.context['challenge']['display']}")

            if model == 'node':
                return f'Hello, node {self.actor_display}!'

            if model == 'file':
                words.append('exported')
                t = len(value)
                words.append(str(t))
                if t == 1:
                    words.append('file')
                elif t > 1:
                    words.append('files')

            if len(words) == 0:
                return f'Could not decode: {self.action} {model} <code>{json.dumps(self.raw_message)}</code>'

            actor = self.actor_display if self.actor_display else self.actor_identifier
            words.insert(0, actor)
            words[-1] += '.'
            return ' '.join(words)
        except Exception as e:
            logging.exception(e)
            return f'Could not decode: {e}'

    @staticmethod
    def from_message(message: Message, raw_event:'Block', raw_message):
        from apps.user.user_profile.models import Profile
        # TODO raw_message is a string but should be a jsonl
        actor_identifier = message.actor.identifier
        actor_qs = Profile.objects.filter_by_identifier(actor_identifier)
        msg = message.model_dump()
        return Log.objects.create(
            event_date=raw_event.date_created, # this is a problem if one wants to correlate blocks across centauron nodes as every block was created at a different time supposely
            action=message.action,
            object=msg.get('object'),
            context=msg.get('context'),
            actor_identifier=actor_identifier,
            actor_display=message.actor.display,
            actor=actor_qs.first(),
            raw_event=raw_event.content_as_json,
            raw_message=raw_message,
            event_id=raw_event.event_id,
            message_id=raw_event.message_hash,
            block_number=raw_event.number
        )

    @staticmethod
    def send_broadcast(message: Message, send_async=False):
        send_broadcast_message_wrapper(topic=settings.FIREFLY_MESSAGE_TOPIC_LOG, data=message.model_dump(), send_async=send_async)


class LastSeenBlock(Base):
    block = models.TextField()


class Block(Base):
    number = models.BigIntegerField()
    tx = models.JSONField()
    message_hash = models.TextField()
    content = models.TextField(default=None, null=True)
    cid = models.TextField()
    tx_content = models.JSONField(default=dict)

    cid_downloaded = models.BooleanField(default=False)

    @property
    def is_broadcast(self):
        return self.tx_content.get('type') == 'broadcast'

    @property
    def is_data_transfer(self):
        return self.tx_content.get('type') == 'data-transfer'

    @property
    def event_id(self):
        return self.tx['hash']

    @property
    def content_as_json(self):
        return json.loads(self.content)
