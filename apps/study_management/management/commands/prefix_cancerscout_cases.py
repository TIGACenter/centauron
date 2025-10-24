from django.core.management.base import BaseCommand

from apps.project.project_case.models import Case
from apps.storage.models import File
from apps.study_management.models import StudyArm


class Command(BaseCommand):
    help = "Prefix all cases with A2020-."

    def handle(self, *args, **options):
        qs = Case.objects.all()
        for f in qs:
            f.name = 'A2020-' + f.name
            f.save(update_fields=['name'])
        print(f'Updated {qs.count()} cases.')
