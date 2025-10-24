import json
import logging
import shutil

from celery import shared_task
from django.conf import settings
from django.db.models import QuerySet

from apps.challenge.challenge_submission.models import Submission, SubmissionLogEntry, SubmissionArtefact
from apps.computing.computing_artifact.models import ComputingJobArtifact
from apps.computing.computing_executions.models import ComputingJobExecution
from apps.computing.computing_log.models import ComputingJobLogEntry
from apps.computing.models import ComputingJobDefinition
from apps.federation.inbox.models import InboxMessage
from apps.federation.messages import UpdateMessage, SubmissionObject, SubmissionResultObject
from apps.federation.outbox.models import OutboxMessage
from apps.permission.models import Permission
from apps.share.api import ShareBuilder
from apps.storage.models import File
from apps.user.user_profile.models import Profile


@shared_task
def send_status(submission_pk: str, status: str):
    submission = Submission.objects.get(pk=submission_pk)
    sender = submission.created_by
    recipient = submission.origin

    object = SubmissionObject(
        content={
            'updated_fields': ['status'],
            'submitter': str(submission.submitter),
            'identifier': str(submission.identifier),
            'status': status
        }
    )

    msg = OutboxMessage.create(sender=sender,
                               recipient=recipient,
                               message_object=object,
                               message_type=UpdateMessage)
    msg.send(send_async=False)


@shared_task
def run_computing_job(submission_pk: str):
    submission = Submission.objects.get(pk=submission_pk)
    submission.computing_job_definition.execute()

# 60 * 60 * 24
@shared_task(soft_time_limit=86400, time_limit=86400)
def send_aggregated_submission_to_submitter(submission_pk, current_user_pk):
    submission = Submission.objects.get(pk=submission_pk)
    current_user = Profile.objects.get(pk=current_user_pk)

    # how to merge the two submissions?
    # idea: get all part submission shares and merge the dictionaries together.
    # this is not the very best solution bc if the share structure changes the changes must be reflected here as well.
    # the leaderboard results are sent at another time so no worries about aggregated results here.

    qs = InboxMessage.objects.filter(message__object__type="submission-result", message__object__content__reference=submission.identifier)
    msg = qs[0].message
    msg['from'] = settings.IDENTIFIER
    msg['to'] = submission.submitter.node.identifier
    object = msg['object']
    object['sender'] = current_user.identifier
    object['recipient'] = submission.submitter.identifier
    content = object['content']
    content['submission'] = content['reference']
    del content['reference']
    c = []
    for m in qs:
        c.append(m.message['object']['content']['content'])

    content['content'] = c

    OutboxMessage.create(
        sender=current_user,
        recipient=submission.submitter,
        message_object=object,
    ).send()



# 60 * 60 * 24
@shared_task(soft_time_limit=86400, time_limit=86400)
def send_results_to_submission_submitter(created_by_pk,
                                         challenge_pk,
                                         definition_pk,
                                         submission_pk,
                                         checked_logs,
                                         checked_artefacts,
                                            execution_pk
                                         ):
    # logs
    stage = None
    log_pks = set()
    stage_pks = set()
    submission = Submission.objects.get(pk=submission_pk)
    cje = ComputingJobExecution.objects.get(pk=execution_pk)

    # add stages of other nodes as well to the stage_pks
    bs = ComputingJobArtifact.objects.filter(
        pk__in=submission.computing_job_executions.distinct().values_list('artifacts', flat=True).distinct())
    for b in bs:
        stage_pks.add(b.computing_job.pk)

    bs = ComputingJobLogEntry.objects.filter(
        pk__in=submission.computing_job_executions.distinct().values_list('log_entries', flat=True).distinct())
    for b in bs:
        stage_pks.add(b.computing_job.pk)

    # sane default: if no log was checked (not reloaded), the send all.
    # TODO this could be wrong if a user is unchecking all log output
    # if len(checked_logs) == 0:
    #     checked_logs = [f'{cje.id}.{log.id}' for log in cje.log_entries.values_list('id', flat=True)]

    for log in checked_logs:
        stage_pk, log_pk = log.split('.')
        log_pks.add(log_pk)
        stage_pks.add(stage_pk)
        if stage is None or stage_pk != stage.id_as_str:
            stage = ComputingJobExecution.objects.get(pk=stage_pk)  # TODO, definition__id=definition_pk)
        log_entry = ComputingJobLogEntry.objects.get(pk=log_pk, computing_job_id=stage_pk)
        log_entry.submission_log_entry.obscure = False
        log_entry.submission_log_entry.save(update_fields=['obscure'])

    obscured_logs = ComputingJobLogEntry.objects.filter(computing_job__in=stage_pks).exclude(id__in=log_pks)
    for l in obscured_logs:
        sle, _ = SubmissionLogEntry.objects.get_or_create(log_entry=l)
        sle.obscure = True
        sle.save(update_fields=['obscure'])

    # TODO add the artefacts of other nodes as well
    # TODO add the logs of other nodes as well

    # artefacts
    artefact_pks = set()
    for artefact in checked_artefacts:
        stage_pk, artefact_pk = artefact.split('.')
        artefact_pks.add(artefact_pk)
        stage_pks.add(stage_pk)
        if stage is None or stage_pk != stage.id_as_str:
            stage = ComputingJobExecution.objects.get(pk=stage_pk)  # TODO, definition__id=definition_pk)
        artefact = ComputingJobArtifact.objects.get(pk=artefact_pk, computing_job_id=stage_pk)
        artefact.submission_artefact.do_not_send = False
        artefact.submission_artefact.save()
    obscured_artefacts = ComputingJobArtifact.objects.filter(computing_job__in=stage_pks).exclude(id__in=artefact_pks)
    for l in obscured_artefacts:
        sle, _ = SubmissionArtefact.objects.get_or_create(artefact=l)
        sle.do_not_send = True
        sle.save(update_fields=['do_not_send'])

    # TODO create the submissionarttefact model for all artefacts from other nodes
    #
    # artefacts = ComputingJobArtifact.objects.filter(
    #     pk__in=submission.computing_job_executions.distinct().values_list('artifacts', flat=True).distinct())
    artefacts = ComputingJobArtifact.objects.filter(pk__in=artefact_pks)
    for a in artefacts:
        # if submission_artefact is None it means that this artefact is coming from another node
        if a.submission_artefact is None:
            SubmissionArtefact.objects.create(artefact=a, do_not_send=False)
        else:
            a.submission_artefact.do_not_send = False
            a.submission_artefact.save(update_fields=['do_not_send'])

    # definition_pks = ComputingJobExecution.objects.filter(id__in=stage_pks, definition__submission=submission).values_list('definition', flat=True).distinct()
    artefacts_to_send = SubmissionArtefact.objects.filter(artefact__computing_job_id__in=stage_pks, do_not_send=False)
    logs_to_send = [l.log_entry for l in
                    SubmissionLogEntry.objects.filter(obscure=False, log_entry__computing_job_id__in=stage_pks)]

    files = [f.artefact.file for f in artefacts_to_send]
    artefacts = [f.artefact for f in artefacts_to_send]

    for f in files:
        Permission.objects.get_or_create(
            user=submission.origin,
            action=Permission.Action.DOWNLOAD,
            object_identifier=f.identifier,
            permission=Permission.Permission.ALLOW,
        )

    created_by = Profile.objects.get(pk=created_by_pk)
    builder = ShareBuilder(name='',
                           pk=None,
                           created_by=created_by,
                           origin=created_by)
    builder.add_file_handler(data=File.objects.filter(id__in=list(map(lambda e: e.id, files))))
    builder.add_permission_handler(data=','.join(list(map(lambda e: f'\'{e.identifier}\'', files))))
    computing_definitions = ComputingJobDefinition.objects.filter(pipeline__is_template=False,
                                                                  id__in=submission.computing_job_executions.values_list(
                                                                      'definition', flat=True).distinct())
    computing_executions = ComputingJobExecution.objects.filter(id__in=stage_pks)
    logs_to_send = ComputingJobLogEntry.objects.filter(id__in=list(map(lambda e: e.pk, logs_to_send)))

    builder.add_computing_job_definition_handler(data=computing_definitions)
    builder.add_computing_job_log_handler(data=logs_to_send)
    builder.add_computing_job_execution_handler(data=computing_executions)
    builder.add_computing_job_artefact_handler(data=artefacts)

    share = builder.build()

    object = SubmissionResultObject(
        content={'submission': str(submission.identifier), 'reference': submission.reference,
                 'content': json.loads(json.dumps(share.content))},
    )

    om = OutboxMessage.create(recipient=submission.origin,
                              # TODO in the federated validation and part submission setting, is this really submission.origin??
                              sender=created_by,
                              message_object=object,
                              extra_data={})
    om.send()


@shared_task
def export_artifacts(computing_execution_pk: str, path: str):
    artifacts: QuerySet[ComputingJobArtifact] = ComputingJobArtifact.objects.filter(
        computing_job_id=computing_execution_pk)

    if artifacts.count() == 0:
        logging.warning('Canceling export job: No artefacts found.')
        return

    path_exporting = path + '.exporting'
    dest = settings.STORAGE_EXPORT_DIR / path_exporting

    for a in artifacts:
        d = dest / a.file.original_path
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(a.file.as_path, d)

    dest.rename(settings.STORAGE_EXPORT_DIR / path)
