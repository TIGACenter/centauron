import json
import uuid

from apps.blockchain.messages import SubmissionSentMessage, Object
from apps.blockchain.models import Log
from apps.challenge.challenge_submission.models import Submission, SubmissionStatus
from apps.challenge.challenge_submission.serializers import SubmissionSerializer
from apps.federation.file_transfer.models import TransferJob, TransferItem
from apps.federation.file_transfer.tasks import create_download
from apps.federation.messages import SubmissionObject
from apps.federation.outbox.models import OutboxMessage
from apps.storage.models import File
from config import celery_app


@celery_app.task
def send_submission_to_challenge_origin(submission_pk):
    submission = Submission.objects.get(pk=submission_pk)

    package = {}
    package['submission'] = SubmissionSerializer(submission).data
    object = SubmissionObject(content=json.loads(json.dumps(package)))
    om = OutboxMessage.create(
        recipient=submission.challenge.origin,
        sender=submission.created_by,
        message_object=object
    )
    om.send()
    SubmissionStatus.objects.create(status=SubmissionStatus.Status.SENT, submission=submission)
    # blockchain log
    Log.send_broadcast(
        SubmissionSentMessage(
            actor=submission.created_by.to_actor(),
            object=Object(model='submission',
                          value={
                              'name': submission.name,
                             'identifier': submission.to_identifiable()
                          }),
            context={'challenge': submission.challenge.to_identifiable()}
        )
    )


@celery_app.task
def create_transfer_job_and_start_for_challenge_client(transfer_job_pk):
    transfer_job = TransferJob.objects.get(pk=transfer_job_pk)
    files_not_imported = File.objects.filter(**transfer_job.query)
    for file in files_not_imported:
        ti = TransferItem.objects.create(file=file,
                                         transfer_job=transfer_job,
                                         created_by=transfer_job.created_by,
                                         download_folder=str(uuid.uuid4()))
        create_download(ti)
