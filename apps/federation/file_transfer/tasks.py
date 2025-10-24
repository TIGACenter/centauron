import logging

import httpx
from django.conf import settings

from apps.federation.file_transfer.backends import get_file_download_backend
from apps.federation.file_transfer.models import TransferItem, TransferJob
from apps.storage.storage_importer.tasks import import_single_file
from config import celery_app

download_backend = get_file_download_backend()()


@celery_app.task
def create_downloads():
    for ti in TransferItem.objects.filter(status=TransferItem.Status.PENDING):
        create_download(ti)


def create_download(transfer_item: TransferItem) -> None:
    if transfer_item.file.origin.node.identifier != settings.IDENTIFIER:
        download_backend.download_file(transfer_item)
    else:
        project = transfer_item.transfer_job.project
        file = transfer_item.file
        project.files.through.objects.filter(user=transfer_item.created_by, file=file).update(imported=True)
        transfer_item.status = TransferItem.Status.COMPLETE
        transfer_item.save(update_fields=["status"])

@celery_app.task
def start_transfer_job(job_pk):
    tj = TransferJob.objects.get(pk=job_pk)
    for i in tj.transfer_items.all():  # TODO filter for pending?
        create_download(i)


# this task actually belongs to the aria2 backend
@celery_app.task
def watch_download_state():
    for ti in TransferItem.objects.filter(
        status__in=[TransferItem.Status.CREATED,
                    TransferItem.Status.PAUSE,
                    TransferItem.Status.WAITING,
                    TransferItem.Status.ACTIVE,
                    TransferItem.Status.PENDING]):
        jsonreq = {'jsonrpc': '2.0', 'id': 'qwer',
                   'method': 'aria2.tellStatus',
                   'params': [f'token:{settings.DOWNLOADER_SECRET}', ti.download_gid,
                              ['gid', 'status', 'errorCode', 'errorMessage']]}
        response = httpx.post(settings.DOWNLOADER_ADDRESS, json=jsonreq)
        if response.status_code == 200:
            result = response.json()['result']
            status = TransferItem.Status[result['status'].upper()]
            ti.status = status
            if status == TransferItem.Status.ERROR:
                ti.error_message = str(result['errorCode']) + ' ' + result['errorMessage']
            ti.save()
        else:
            result = response.json()
            if 'error' in result:
                if 'code' in result['error']:
                    pass
                    # TODO this would also be the case for stopped and errored downloads
                    # if result['error']['code'] == 1:
                    #     ti.download_gid = None
                    #     ti.status = TransferItem.Status.COMPLETE
                    #     ti.save()
            logging.warning('Response from aria2 was not http code 200: %s %s', response.status_code, response.text)


@celery_app.task
def import_completed_downloads(transfer_item_pk=None):
    logging.info('Importing completed download for %s', transfer_item_pk)
    ti = TransferItem.objects.get(pk=transfer_item_pk)
    downloaded_file_tmp = settings.DOWNLOADER_TMP_DIR  # / Path(ti.download_folder) / ti.file.name
    if ti.download_folder is not None and len(ti.download_folder.strip()) > 0:
        downloaded_file_tmp /= ti.download_folder
    downloaded_file_tmp /= ti.file.name
    if not downloaded_file_tmp.exists():
        ti.delete()  # TODO is this ok here??
        logging.error('Downloaded file does not exist @ %s. Canceling import.', downloaded_file_tmp)
        return
    import_single_file(ti.file, downloaded_file_tmp, remove_src_folder=False)


@celery_app.task
def remove_download_from_aria2(transfer_item_pk):
    ti = TransferItem.objects.filter(pk=transfer_item_pk, file__imported=False)
    if not ti.exists():
        return
    ti = ti.first()
    if not ti.removed:
        jsonreq = {'jsonrpc': '2.0', 'id': 'qwer',
                   'method': 'aria2.removeDownloadResult',
                   'params': [f'token:{settings.DOWNLOADER_SECRET}', ti.download_gid]}
        response = httpx.post(settings.DOWNLOADER_ADDRESS, json=jsonreq)
        if response.status_code != 200:
            logging.error('Could not purge completed downloads: %s', response.text)


@celery_app.task
def purge_downloads_from_aria2():
    jsonreq = {'jsonrpc': '2.0', 'id': 'qwer',
               'method': 'aria2.purgeDownloadResult',
               'params': [f'token:{settings.DOWNLOADER_SECRET}']}
    response = httpx.post(settings.DOWNLOADER_ADDRESS, json=jsonreq)
    if response.status_code != 200:
        logging.error('Could not purge downloads: %s', response.text)


@celery_app.task
def post_process_complete_downloads():
    # remove from aria2 to prevent re-downloading after aria2 restart
    for ti in TransferItem.objects.filter(status__in=[TransferItem.Status.COMPLETE], file__imported=False):
        import_completed_downloads(transfer_item_pk=ti.id_as_str)
        if not ti.removed:
            # remove download and import file
            # remove_download_from_aria2(ti.id_as_str)
            # import_completed_downloads(ti.id_as_str)
            remove_download_from_aria2(ti.id_as_str)  # .apply_async(kwargs={'transfer_item_pk': ti.id_as_str},
            #                                        link=import_completed_downloads.s(ti.id_as_str))
