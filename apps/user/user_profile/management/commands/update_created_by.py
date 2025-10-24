from django.core.management.base import BaseCommand
from django.apps import apps

from apps.user.user_profile.models import Profile


class Command(BaseCommand):
    help = 'Update created_by field for all models from one user to another.'

    def add_arguments(self, parser):
        parser.add_argument(
            'old_identifier',
            type=str,
            help='Identifier of the user to replace (old user).'
        )
        parser.add_argument(
            'new_identifier',
            type=str,
            help='Identifier of the user to replace with (new user).'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Perform a dry run without making changes.'
        )

    def handle(self, *args, **options):
        old_user_id = options['old_identifier']
        new_user_id = options['new_identifier']
        dry_run = options['dry_run']

        old_user = Profile.objects.get(identifier=old_user_id)
        new_user = Profile.objects.get(identifier=new_user_id)

        if not old_user:
            self.stderr.write(f"Error: User with ID {old_user_id} does not exist.")
            return
        if not new_user:
            self.stderr.write(f"Error: User with ID {new_user_id} does not exist.")
            return

        all_models = apps.get_models()
        total_updates = 0

        for model in all_models:
            if 'created_by' in [field.name for field in model._meta.fields]:
                queryset = model.objects.filter(created_by=old_user)
                count = queryset.count()

                if count > 0:
                    self.stdout.write(
                        f"Found {count} instances in {model.__name__} with created_by={old_user}."
                    )

                    if not dry_run:
                        queryset.update(created_by=new_user)
                        self.stdout.write(
                            f"Updated {count} instances in {model.__name__}."
                        )
                    total_updates += count

        if dry_run:
            self.stdout.write(
                f"Dry run complete. Total records that would be updated: {total_updates}."
            )
        else:
            self.stdout.write(f"Update complete. Total records updated: {total_updates}.")
