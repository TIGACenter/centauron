from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Imports a node from a given identifier."

    def add_arguments(self, parser):
        parser.add_argument('identifier', nargs='+')

    def handle(self, *args, **options):
        # TODO check if node is already imported
        # TODO query CCA
        # TODO write a method that sets the node for all users that do not have a node yet and which identifier starts with the node identifier
        # TODO if a profile is created during import of a file or so the node is not known so it is not set
        # Node.create_from_node_data
        raise NotImplementedError()

