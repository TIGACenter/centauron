from django.core.management.base import BaseCommand

from apps.share.models import Share


class Command(BaseCommand):
    help = 'Deletes a share.'

    def add_arguments(self, parser):
        parser.add_argument('share_identifier', nargs='+', type=str)

    def handle(self, *args, **options):
        qs = Share.objects.filter(identifier=options['share_identifier'][0])
        if qs.exists():
            qs.first().delete()
