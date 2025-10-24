from django.core.management.base import BaseCommand

from apps.study_management.models import StudyArm


class Command(BaseCommand):
    help = "Fixes the case names of a specific study."

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
        case_renamed = []

        for arm in study_arm:
            files = arm.files.all()
            for f in files:
                if f.case_id not in case_renamed:
                    case = f.case
                    old_name = case.name
                    if case.name.startswith('RE'):
                        case.name = case.name[3:9]
                    # A2020-000549_1-1-
                    if case.name.startswith('A2020'):
                        case.name = case.name[6:12]
                    self.stdout.write(f'{old_name} --> {case.name}')
                    if not dry_run:
                        case.save(update_fields=['name'])




