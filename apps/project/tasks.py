import uuid

from apps.federation.file_transfer.models import TransferItem, TransferJob
from apps.federation.file_transfer.tasks import create_download
from apps.share.models import Share
from config import celery_app


@celery_app.task
def create_transfer_items_for_share(created_by_id, share_pk):
    share = Share.objects.get(pk=share_pk)
    for file in share.files.all():
        TransferItem.objects.create(file=file,
                                    created_by_id=created_by_id,
                                    download_folder=str(uuid.uuid4()))


@celery_app.task
def create_transfer_job_and_start(transfer_job_pk, query, in_project=True):
    tj = TransferJob.objects.get(pk=transfer_job_pk)
    if in_project:
        query['projects'] = tj.project

    # q = {}
    # if 'id__in' in query:
    #     q['file_id__in'] = query['id__in']

    # files_not_imported = tj.project.files.through.objects.filter(user=tj.created_by, imported=False, **q).distinct()
    files_not_imported = tj.project.files_for_user(tj.created_by).filter(imported=False, **query)
    create_transfer_items_for_files_and_start(tj, files_not_imported)

def create_transfer_items_for_files_and_start(transfer_job, files):
    for file in files:
        ti = TransferItem.objects.create(file=file,
                                         transfer_job=transfer_job,
                                         created_by=transfer_job.created_by,
                                         download_folder=str(uuid.uuid4()))
        create_download(ti)
