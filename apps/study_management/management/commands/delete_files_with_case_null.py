from django.core.management.base import BaseCommand

from apps.project.project_case.models import Case
from apps.storage.models import File
from apps.study_management.models import StudyArm


class Command(BaseCommand):
    help = "Delete files with case = null."

    def handle(self, *args, **options):
        qs = File.objects.filter(case__isnull=True)
        for f in qs:
            f.delete()
        print(f'Deleted {qs.count()} files.')
