from django.core.management.base import BaseCommand

from apps.project.project_case.models import Case
from apps.storage.models import File
from apps.study_management.models import StudyArm


class Command(BaseCommand):
    help = "Delete cases that are only numeric."

    def handle(self, *args, **options):
        qs = Case.objects.all()
        for f in qs:
            if len(f.name) < 6:
                f.delete()
