import urllib
import uuid

import urllib
from django.conf import settings
from django.db import models

from apps.core.models import Base, CreatedByMixin

class TransferItem(CreatedByMixin, Base):
    class Status(models.TextChoices):
        PENDING = 'pending'  # created in this application but not yet created in the downloader
        CREATED = 'created'  # created in the downloader
        WAITING = 'waiting'  # download not yet started
        ACTIVE = 'active'  # currently downloading
        PAUSE = 'paused'  # paused
        COMPLETE = 'complete'  # stopped or completed downloads
        ERROR = 'error'  # stopped due to error
        REMOVED = 'removed'

    download_gid = models.CharField(max_length=100, null=True)
    download_folder = models.CharField(max_length=100, blank=True, null=True)
    error_message = models.TextField(default=None, null=True, blank=True)
    file = models.ForeignKey('storage.File', on_delete=models.CASCADE, related_name='transfers')
    status = models.CharField(choices=Status.choices, default=Status.PENDING, max_length=20)
    transfer_job = models.ForeignKey('TransferJob', on_delete=models.CASCADE, related_name='transfer_items')

    def __str__(self):
        return f'{self.file} ({self.status})'

    @property
    def processed(self):
        return self.status in [TransferItem.Status.ERROR, TransferItem.Status.COMPLETE]

    @property
    def processing(self):
        return not self.processed

    @property
    def removed(self):
        return self.status == TransferItem.Status.COMPLETE and self.download_gid is None


class TransferJob(CreatedByMixin, Base):
    project = models.ForeignKey('project.Project', null=True, blank=True, on_delete=models.CASCADE,
                                related_name='transfer_jobs')
    query = models.JSONField(default=dict, blank=True)

    def restart(self):
        self.transfer_items.filter(status=TransferItem.Status.ERROR).update(status=TransferItem.Status.PENDING)
        self.start()

    def start(self):
        from apps.federation.file_transfer.tasks import start_transfer_job
        start_transfer_job.delay(self.id_as_str)

    def kill(self):
        from apps.federation.file_transfer.tasks import remove_download_from_aria2
        items = self.transfer_items.filter(
            status__in=[TransferItem.Status.ERROR, TransferItem.Status.PENDING, TransferItem.Status.ACTIVE])
        for i in items:
            remove_download_from_aria2.delay(i.id_as_str)

    @property
    def status(self):
        if self.transfer_items.filter(status=TransferItem.Status.ERROR).exists():
            return TransferItem.Status.ERROR
        if self.transfer_items.filter(status=TransferItem.Status.ACTIVE).exists():
            return TransferItem.Status.ACTIVE
        if self.transfer_items.filter(status=TransferItem.Status.COMPLETE).count() == self.transfer_items.count():
            return TransferItem.Status.COMPLETE
        return TransferItem.Status.PENDING

    def status_is_error(self):
        return self.status == TransferItem.Status.ERROR

    def status_is_active(self):
        return self.status == TransferItem.Status.ACTIVE

    def status_is_complete(self):
        return self.status == TransferItem.Status.COMPLETE

    def status_is_pending(self):
        return self.status == TransferItem.Status.PENDING


'''
* aria2 as download server
* communicate with aria2 via json-rpc interface (basically http, see aria2 docs @ https://aria2.github.io/manual/en/html/aria2c.html#methods)
* download link: encode identifier in uri as GET parameter
* aria2 returns a GID for each download
* in the transfer model, store the GID and current state
* use a celery task to periodically query the state of the download (via GID). As an alternative, figure out how to start a websocket connection next to django without needing a new docker container and create a websocket connection for notifications. this is actually preferred as it is more real time.
* provide certificate and private key of certificate authentication when starting the rpc connection
* models:
    * TransferSession
    * TransferItem
    *

'''


def generate_token():
    return str(uuid.uuid4())


class DownloadToken(CreatedByMixin, Base):
    class Meta:
        constraints = [
            models.UniqueConstraint(name='unique_file_token', fields=('file', 'token')),
            models.Index(name='token_idx', fields=['token'])
        ]

    file = models.ForeignKey('storage.File', on_delete=models.CASCADE, related_name='download_tokens')
    # TODO this must be a user on this node
    for_user = models.ForeignKey('user_profile.Profile', on_delete=models.CASCADE, related_name='download_tokens')
    token = models.CharField(max_length=50, default=generate_token)
    challenge = models.ForeignKey('challenge.Challenge', on_delete=models.CASCADE, related_name='download_tokens', null=True, blank=True)

    def build_url(self):
        identifier = urllib.parse.quote_plus(self.file.identifier)
        return f'{settings.DOWNLOAD_ADDRESS}?id={identifier}&token={self.token}'
