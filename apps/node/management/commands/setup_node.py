from django.conf import settings
from django.core.management.base import BaseCommand

from apps.node.models import Node


class Command(BaseCommand):
    help = "Sets up a shiny new node with the data based on the given environment variables."

    def handle(self, *args, **options):
        try:
            Node.objects.get_me()
            self.stderr.write('Node is already set up.')
        except Node.DoesNotExist:
            self.stderr.write('Node is not yet set up.')
            Node.objects.create(identifier=settings.IDENTIFIER,
                                human_readable=settings.NODE_NAME,
                                api_address=settings.API_ADDRESS,
                                did=settings.ORGANIZATION_DID)

