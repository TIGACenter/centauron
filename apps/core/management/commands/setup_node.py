from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand

from apps.node.models import Node

User = get_user_model()


class Command(BaseCommand):
    help = "Sets the node up."

    def handle(self, *args, **options):
        n, created = Node.objects.get_or_create(identifier=settings.IDENTIFIER)
        n.address_fhir_server = settings.FHIR_SERVER
        n.address_centauron = settings.ADDRESS
        n.common_name = settings.COMMON_NAME
        n.human_readable = settings.NODE_NAME
        n.api_address = settings.API_ADDRESS
        n.save()
        if created:
            self.stdout.write('Node created.')
        else:
            self.stdout.write('Node updated.')

        u, created = User.objects.get_or_create(username='node')
        if created:
            u.profile.identifier = settings.IDENTIFIER
            u.profile.node = n
            u.profile.human_readable = 'Node'
            u.profile.identity = settings.ORGANIZATION_DID
            u.profile.save()
            self.stdout.write('User node created.')
        else:
            self.stdout.write('User node already exists.')

        call_command('create_periodic_tasks')

