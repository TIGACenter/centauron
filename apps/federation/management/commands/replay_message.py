import logging

from django.core.management.base import BaseCommand

from apps.federation.inbox.models import InboxMessage
from apps.federation.inbox.tasks import process_inbox_message
from apps.federation.outbox.models import OutboxMessage
from apps.federation.outbox.tasks import send_outbox_message


class Command(BaseCommand):
    help = "Replays a message."

    def add_arguments(self, parser):
        parser.add_argument('id', nargs='+')

    def handle(self, *args, **options):
        id = options['id'][0]

        qs = InboxMessage.objects.filter(id=id)
        if not qs.exists():
            qs = OutboxMessage.objects.filter(id=id)
            if not qs.exists():
                logging.error("No inbox or outbox message found with provided id.")
                return
            else:
                m = send_outbox_message
        else:
            m = process_inbox_message

        obj = qs.first()
        obj.processed = False
        obj.processing = False
        obj.save()
        m(obj.id_as_str)
