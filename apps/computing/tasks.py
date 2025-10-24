import logging
from typing import Any, Dict

from celery import shared_task
from django.conf import settings

from apps.blockchain.messages import UseMessage, Object
from apps.blockchain.models import Log
from apps.challenge.challenge_submission.models import SubmissionStatus, Submission, SubmissionToNodes
from apps.challenge.challenge_submission.tasks import send_status
if settings.ENABLE_COMPUTING:
    from apps.computing.computing_executions.backend import computing_backend
from apps.computing.computing_executions.models import ComputingJobExecution
from apps.computing.models import ComputingJobDefinition
from apps.user.user_profile.models import Profile


@shared_task
def start_task_from_computing_execution(created_by_pk: str, computing_execution_pk: str):
    # TODO continue implementing here
    pass


@shared_task
def send_submission_run_event(computing_definition_pk: str,
                              submission_pk: str):
    cdef = ComputingJobDefinition.objects.get(pk=computing_definition_pk)
    submission = Submission.objects.get(pk=submission_pk)

    # with (settings.STORAGE_DATA_DIR / cdef.data_file).open() as f:
    #     ids = f.read().splitlines()
    files = cdef.data_entities
    if files is not None:
        files = files.values_list('identifier', flat=True)
    else:
        files = []
    # file_identifiers = File.objects.filter(pk__in=ids).values_list('identifier', flat=True)
    msg = UseMessage(actor=cdef.created_by.to_actor(), object=Object(model="slide", value=files),
                     context={'submission': submission.to_identifiable(),
                              'challenge': submission.challenge.to_identifiable()})
    Log.send_broadcast(msg)


@shared_task
def start_task_from_computing_definition(created_by_pk: str,
                                         computing_definition_pk: str,
                                         execution_before_pk: str | None = None,
                                         environment_variables: Dict[str, Any] = dict,
                                         submission_pk=None):
    if not settings.ENABLE_COMPUTING:
        logging.warning('Computing is disabled on this node.')
        return

    cdef = ComputingJobDefinition.objects.get(pk=computing_definition_pk)

    created_by = Profile.objects.get(pk=created_by_pk)
    submission_given = submission_pk is not None
    submission = None
    if submission_given:
        submission = Submission.objects.get(pk=submission_pk)

    if cdef.submission is None and submission_given:
        cdef.submission = submission
        cdef.save(update_fields=['submission'])

    if not cdef.is_post:  # TODO: evaluate: not is_post and type_is_manual
        # pull and re-tag docker image
        cdef.push_and_pull_docker_image_to_private_repository(cdef)

    # 1. create execution from definition
    executions = ComputingJobExecution.from_definition(created_by, cdef)
    # TODO add this execution to the submission

    # TODO set execution_before if job definition has already some executions. take one of the previous executions
    # TODO the next if most definitely will not work in the batched scenario
    for ex in executions:
        if submission_given:
            submission.computing_job_executions.add(ex)
        if cdef.execution_type_is_auto:
            execution_before_pk_not_none = execution_before_pk is not None
            if cdef.has_executions or execution_before_pk_not_none:
                e_b = None
                if execution_before_pk_not_none:
                    e_b = ComputingJobExecution.objects.get(pk=execution_before_pk)
                elif cdef.has_executions:
                    e_b = cdef.executions.first().executed_after.first()  # TODO is this correct?
                if e_b is not None:
                    ex.executed_after.add(e_b)

            computing_backend.prepare(ex)
            # 2. start definition
            computing_backend.execute(ex)
    else:
        # only set the status. the user can now proceed to perform the manual task in the user interface.
        ex.status = ComputingJobExecution.Status.CREATED
        ex.save(update_fields=['status'])


@shared_task
def start_stage_from_last(last_computing_job_execution_def_pk):
    previous_stage_definition: ComputingJobExecution = ComputingJobExecution.objects.get(
        pk=last_computing_job_execution_def_pk)

    # check all stage instances of the previous stage. if previous stage has any instance with status NOT success,
    # then do not start the next one.
    if previous_stage_definition.definition.is_batched and previous_stage_definition.definition.executions.filter(
        status=ComputingJobExecution.Status.SUCCESS).count() < previous_stage_definition.definition.total_batches:
        logging.info('Some batches did not finish yet with status success. Therefore not starting the next stage.')
        return
    elif previous_stage_definition.executed_before is not None and not previous_stage_definition.executed_before.is_success:
        logging.info('Some StageInstances did not finish with status success. Therefore not starting the next stage.')
        # TODO send status error and maybe? include error message
        return

    next_stage: ComputingJobDefinition = previous_stage_definition.definition.next()
    submission_id = None
    submission = previous_stage_definition.submissions.first()
    if submission is not None:
        submission_id = submission.id_as_str
    if next_stage is not None:
        start_task_from_computing_definition(str(previous_stage_definition.created_by_id), next_stage.id_as_str,
                                             previous_stage_definition.id_as_str,
                                             submission_pk=submission_id)
    else:
        logging.info('No other stage. computing job is done.')
        # extract target metrics from output of this stage.
        if previous_stage_definition.definition.is_post:
            previous_stage_definition.definition.pipeline.submission.extract_target_metrics(previous_stage_definition)
        if previous_stage_definition.definition.pipeline is not None and previous_stage_definition.definition.pipeline.submission is not None:
            send_status(previous_stage_definition.definition.pipeline.submission.id_as_str,
                              SubmissionStatus.Status.EXECUTED)

        submission_to_node = SubmissionToNodes.objects.filter(submission=submission, node=submission.challenge.origin)
        if submission_to_node.exists():
            sn = submission_to_node.first()
            sn.status = SubmissionToNodes.Status.RESULTS
            sn.save(update_fields=['status'])

        # TODO set the submission to node of the current node (if applicable) to status success
        # if submission_id is not None:
        #     s = Submission.objects.get(pk=submission_id)
        #     s.submissiontonodes_set.filter(node)
