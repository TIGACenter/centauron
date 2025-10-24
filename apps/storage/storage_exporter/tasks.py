import logging
import shutil
import uuid
from pathlib import Path

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from apps.blockchain.messages import ExportMessage, Object
from apps.blockchain.models import Log
from apps.storage.models import File
from apps.storage.storage_exporter.models import ExportJob


@shared_task(soft_time_limit=60 * 60 * 24)
def export_files(dst: str, identifiers: list[str]):
    # TODO for large directories export in subfolders with 1000 files each or so
    suffix = '.exporting'
    path = settings.STORAGE_EXPORT_DIR / (dst + suffix)
    path.mkdir(parents=True)

    # TODO some tests if requester may actually export files or not
    files = File.objects.filter(identifier__in=identifiers, imported=True)
    for f in files:
        src = f.as_path
        dst = get_unique_filename(path / f.original_path, f)
        logging.info('Copy %s to %s.', src, dst)
        shutil.copy(src, dst)

    dst = Path(str(path.absolute())[:len(str(path.absolute())) - len(suffix)])
    logging.info('Renaming %s to %s.', path, dst)
    shutil.move(path, dst)
    logging.info('Exporting to %s done.', path)


@shared_task(bind=True, soft_time_limit=60 * 60 * 24)
def export_from_job(self, job_pk: str):
    job = ExportJob.objects.get(pk=job_pk)
    job.status = ExportJob.Status.RUNNING
    job.celery_task_id = self.request.id
    job.save(update_fields=['export_folder', 'status', 'celery_task_id'])

    file_identifiers = job.files.values_list('identifier', flat=True)
    export_files(job.export_folder, file_identifiers)

    job.status = ExportJob.Status.SUCCESS
    job.save(update_fields=['status'])

    Log.send_broadcast(ExportMessage(actor=job.created_by.to_actor(), object=Object(model="file", value=file_identifiers),
                                     context={'challenge': job.challenge.to_identifiable()}))


def get_unique_filename(path: Path, file: File):
    if path.exists():
        new_filename = f'{path.stem}-{file.id}.{path.suffix}'
        return path.parent / new_filename
        # return get_unique_filename(path.parent / new_filename, file)
    return path
