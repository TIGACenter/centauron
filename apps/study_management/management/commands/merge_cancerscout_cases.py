from django.core.management.base import BaseCommand

from apps.project.project_case.models import Case
from apps.study_management.models import StudyArm


class Command(BaseCommand):
    help = "Merges files that have the sam case name to a single case."

    def add_arguments(self, parser):
        parser.add_argument('study_id', nargs='+')
        parser.add_argument(
            '--dry',
            action='store_true',  # When included, sets args.dry to True
            help="Perform a dry run without saving changes (default is False)"
        )

    def handle(self, *args, **options):
        study_arm = StudyArm.objects.filter(study_id=options['study_id'][0])
        dry_run = options['dry']

        for arm in study_arm:
            files = arm.files.all()
            for f in files:
                # get all cases with the same name
                cases = Case.objects.filter(name=f.case.name).order_by('name')
                first = cases.first()
                for c in cases:
                    if c.pk == first.pk:
                        continue

                    # move all files to the first case
                    for cf in c.files.all():
                        self.stdout.write(f'{cf.case_id} -> {first.id}')
                        cf.case = first

                        if not dry_run:
                            cf.save(update_fields=['case'])

        # delete all cases that have no files
        cases = Case.objects.all()
        for c in cases:
            if c.files.count() == 0:
                Case.objects.filter(pk=c.pk).delete()
