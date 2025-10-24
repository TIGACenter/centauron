import logging

from celery import shared_task
from django.db.models import Sum
import logging

from apps.storage.fileset.models import FileSet


@shared_task(soft_time_limit=60*60*24)
def update_tilesets_file_count():
    logging.info('Start updating fileset file count.')
    ts = FileSet.objects.all()
    for t in ts:
        logging.info('Updating %s', t)
        t.files_count = t.files.count()
        qs_imported = t.files.filter(imported=True)
        t.files_imported_count = qs_imported.count()
        t.files_total_size = t.files.aggregate(Sum('size'))['size__sum']
        t.files_imported_total_size = qs_imported.aggregate(Sum('size'))['size__sum']
        if t.files_total_size is None:
            t.files_total_size = 0
        if t.files_imported_total_size is None:
            t.files_imported_total_size = 0

        # print(t.files_count, t.files_imported_count, t.files_total_size, t.files_imported_total_size)

        t.save(update_fields=['files_count', 'files_imported_count', 'files_total_size', 'files_imported_total_size'])
    logging.info('Done updating fileset file count.')
