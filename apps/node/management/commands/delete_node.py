from django.core.management.base import BaseCommand

from apps.node.models import Node
from apps.storage.models import File


class Command(BaseCommand):
    help = "Deletes a node."

    def add_arguments(self, parser):
        parser.add_argument('node_identifier', nargs='+')

    def handle(self, *args, **options):
        id = options.get('node_identifier')
        if id is None or len(id) == 0:
            self.stderr.write('No node identifier given.')
        id = id[0].strip()
        f, _ = File.objects.filter(origin__node__identifier=id).delete()
        a, _ = Node.objects.filter(identifier=id).delete()

        self.stdout.write(f'{a+f} object(s) deleted.')
