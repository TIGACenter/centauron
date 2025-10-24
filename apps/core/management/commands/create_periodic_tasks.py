from django.core.management.base import BaseCommand
from django_celery_beat.models import IntervalSchedule, PeriodicTask


class Command(BaseCommand):
    help = "Creates all periodic tasks."

    def handle(self, *args, **options):
        self.stdout.write('Create periodic tasks.')
        interval_1_min, _ = IntervalSchedule.objects.get_or_create(period=IntervalSchedule.MINUTES,
                                                                   every=1)

        # storage
        PeriodicTask.objects.get_or_create(
            interval=interval_1_min,
            name='Import files',
            task='apps.storage.storage_importer.tasks.run_file_importer'
        )

        # download files
        PeriodicTask.objects.get_or_create(
            interval=interval_1_min,
            name='Watch downloads state',
            task='apps.federation.file_transfer.tasks.watch_download_state'
        )

        PeriodicTask.objects.get_or_create(
            interval=interval_1_min,
            name='Postprocess complete downloads',
            task='apps.federation.file_transfer.tasks.post_process_complete_downloads'
        )

        PeriodicTask.objects.get_or_create(
            interval=interval_1_min,
            name='Cleanup pod errors',
            task='apps.computing.computing_executions.backend.k8s.tasks.cleanup_pod_errors'
        )

        self.stdout.write('Done.')
