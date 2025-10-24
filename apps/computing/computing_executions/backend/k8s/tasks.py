import base64
import json
import logging
import shutil
import uuid
from pathlib import Path
from typing import Any, Dict

import kubernetes.config
from celery import shared_task
from django.conf import settings
from django.utils import timezone
from kubernetes import client
from kubernetes.client import ApiException, V1Namespace, V1ObjectMeta, V1Container, V1VolumeMount, V1EnvVar, \
    V1EnvVarSource, V1ObjectFieldSelector, V1Pod, V1Volume, V1EmptyDirVolumeSource, V1HostPathVolumeSource, V1PodSpec, \
    V1Secret
from rest_framework.authtoken.models import Token

from apps.computing.computing_executions.models import ComputingJobExecution
from apps.computing.computing_log.models import ComputingJobLogEntry
from config import celery_app

if settings.ENABLE_COMPUTING:
    kubernetes.config.load_kube_config(config_file=settings.COMPUTING_K8S_CONFIG_FILE)
    k8s_batch_api = kubernetes.client.BatchV1Api()
    k8s_core_api = kubernetes.client.CoreV1Api()


# fix by https://stackoverflow.com/questions/72590062/how-to-get-list-of-events-using-the-python-kubernetes-api
# This is descriptor, see https://docs.python.org/3/howto/descriptor.html
class FakeEventTime:
    def __get__(self, obj, objtype=None):
        return obj._event_time

    def __set__(self, obj, value):
        obj._event_time = value


# Monkey-patch the `event_time` attribute of ` the V1beta1Event class.
client.CoreV1Event.event_time = FakeEventTime()


@celery_app.task
def start_job(job_pk):
    job = ComputingJobExecution.objects.get(pk=job_pk)
    logging.info('Starting job %s', job.definition.name)
    namespace = job.definition.namespace if job.definition.namespace is not None and len(
        job.definition.namespace.strip()) > 0 else 'default'
    # create the namespace
    try:
        k8s_core_api.read_namespace(name=namespace)
        logging.info('Namespace %s already exists.', namespace)
    except ApiException as e:
        if e.status == 404:
            logging.info('Namespace %s does not exist yet. Creating.', namespace)
            k8s_core_api.create_namespace(V1Namespace(metadata=V1ObjectMeta(
                name=namespace
            )))
            if settings.DOCKER_CONFIG_FILE is not None:
                logging.info('Create docker-credentials k8s secret for namespace %s', namespace)
                # create docker secret now
                with open(settings.DOCKER_CONFIG_FILE) as f:
                    docker_config_dict = json.load(f)
                config = base64.b64encode(
                    json.dumps(docker_config_dict).encode("utf-8")
                ).decode("utf-8")
                secret = V1Secret(type='kubernetes.io/dockerconfigjson',
                                  metadata=V1ObjectMeta(name=settings.PRIVATE_DOCKER_REGISTRY_K8S_SECRET_NAME),
                                  data={'.dockerconfigjson': config})
                k8s_core_api.create_namespaced_secret(namespace, secret)
                # microk8s kubectl create secret generic docker-tiga \
                #     --from-file=.dockerconfigjson=/home/ak/.docker/config.json \
                #     --type=kubernetes.io/dockerconfigjson --namespace chal
            else:
                logging.error('Env DOCKER_CONFIG_FILE not set. Cannot create docker-credentials secret on k8s.')
        else:
            logging.exception(e)
            return

    pod: V1Pod = serialize_to_k8s(job.definition.k8s_spec, 'V1Pod')
    volumes = []
    volume_mounts = []
    # TODO only create input and output volume if there is any input or output in this instance
    output_tmp_volume_name = 'output-tmp'
    output_tmp_volume = V1Volume(name=output_tmp_volume_name, empty_dir=V1EmptyDirVolumeSource())
    volumes.append(output_tmp_volume)
    output_tmp_volume_mount = V1VolumeMount(mount_path=f'/output_tmp', name=output_tmp_volume_name)
    volume_mounts.append(output_tmp_volume_mount)

    output_volume_name = 'output'
    output_directory = job.artifact_path
    logging.debug('Creating output dir %s', output_directory)
    if output_directory.exists(): shutil.rmtree(output_directory)
    output_directory.mkdir(parents=True)
    output_path = output_directory.relative_to(settings.COMPUTING_ARTIFACT_DIRECTORY)
    output_volume = V1Volume(name=output_volume_name,
                             host_path=V1HostPathVolumeSource(type='Directory', path=str(
                                 settings.HOST_COMPUTING_ARTIFACT_DIRECTORY / output_path)))
    volumes.append(output_volume)

    computing_task_volume_mounts = []
    data_volume_mount = None
    pod_spec: V1PodSpec = pod.spec

    container_copy_input = list(filter(lambda e: e.name == 'copy-input', pod_spec.init_containers or []))
    needs_data_volume = len(container_copy_input) > 0 or job.definition.has_datafile  # or job.definition.has_files
    if needs_data_volume:
        data_volume_name = 'data'
        data_volume = V1Volume(name=data_volume_name,
                               host_path=V1HostPathVolumeSource(type='Directory',
                                                                path=str(settings.HOST_K8S_DATA_DIRECTORY)))
        # TODO k8s nodes need to have the host directory mounted under the same path
        data_volume_mount = V1VolumeMount(mount_path=f'/data/', name=data_volume_name, read_only=True)
        computing_task_volume_mounts += [data_volume_mount]
        volumes.append(data_volume)

    tmp_volume_name = 'tmp'
    tmp_folder = job.get_tmp_dir(False)  # get the folder on the host to create dir.
    tmp_folder.mkdir(parents=True)
    tmp_folder = job.get_tmp_dir(True)  # get the folder path as mounted on k8s pods.
    tmp_volume = V1Volume(name=tmp_volume_name,
                          host_path=V1HostPathVolumeSource(type='Directory', path=str(tmp_folder)))
    tmp_volume_mount = V1VolumeMount(mount_path='/centauron_tmp/', name=tmp_volume_name)
    computing_task_volume_mounts.append(tmp_volume_mount)
    volumes.append(tmp_volume)

    # mount data file
    if job.definition.has_datafile:
        # add data_file_path as file hostpath volume read only
        # TODO if job is batched, write a temporary data.csv file into the tmp folder and mount that one. only write the entries of the batch into the file
        if job.definition.is_batched:
            # job.def
            # write only the entries for the specific batch into the mounted data.csv file.

            tmp_folder = settings.HOST_K8S_TMP_DIRECTORY / str(uuid.uuid4())
            tmp_folder.mkdir(parents=True)
            tmp_input_file = tmp_folder / f'{uuid.uuid4()}.csv'
            with (settings.STORAGE_DATA_DIR / job.definition.data_file).open('r') as f, tmp_input_file.open('w') as g:
                s = job.batch_number * job.definition.batch_size
                e = job.batch_number * job.definition.batch_size + job.definition.batch_size
                # TODO do it like this or use job.input.all() but then the format of the csv file is not totally clear.
                all_lines = f.readlines()
                lines = all_lines[s + 1:e + 1]  # +1 for the csv header row
                # TODO the whole file +is read into memory so this is the most memory-intensive solution
                g.write(all_lines[0])
                g.writelines(lines)
        else:
            tmp_input_file = settings.HOST_K8S_DATA_DIRECTORY / job.definition.data_file

        data_file_name = 'data.csv'
        volume_mount_name = f'data-file-{data_file_name.replace(".", "-")}-{job.id_as_str}'
        data_file = V1Volume(name=volume_mount_name,
                             host_path=(V1HostPathVolumeSource(type='File', path=str(tmp_input_file))))
        computing_task_volume_mounts += [
            V1VolumeMount(mount_path=f'/data.csv', read_only=True, name=volume_mount_name)]
        volumes.append(data_file)

    env_vars_sidecar = [V1EnvVar(name=f'Q_{key}', value=val) for key, val in
                        job.definition.environment_variables_job_context.items()]

    # TODO add this as secret to k8s
    # TODO this must be the token of the submitting user so it runs with the same permissions.
    token = get_auth_token(job.definition.created_by)
    helper_container = V1Container(
        name='helper',
        volume_mounts=[
            # helper_volume_mount,
            V1VolumeMount(mount_path=f'/output_tmp/',
                          name=output_tmp_volume_name),
            V1VolumeMount(mount_path=f'/output/', name=output_volume_name)
        ],
        image=settings.COMPUTING_K8S_SIDECAR_IMAGE_TAG,
        command=settings.COMPUTING_K8S_SIDECAR_CONTAINER_CMD,
        image_pull_policy='Always',
        env=[
            V1EnvVar(name='VOLUME', value='/helper'),
            V1EnvVar(name='POLL_ATTEMPTS', value='20'),
            V1EnvVar(name='POLL_INTERVAL', value='20'),
            V1EnvVar(name='VOLUME', value='/helper'),
            V1EnvVar(name='RUNNING_ON_NODE', value_from=V1EnvVarSource(
                field_ref=V1ObjectFieldSelector(field_path='spec.nodeName')
            )),
            V1EnvVar(name='POD_NAME', value_from=V1EnvVarSource(
                field_ref=V1ObjectFieldSelector(field_path='metadata.name')
            )),
            V1EnvVar(name='K8S_NAMESPACE', value_from=V1EnvVarSource(
                field_ref=V1ObjectFieldSelector(field_path='metadata.namespace')
            )),
            V1EnvVar(name='JOB_PK', value=job_pk),
            V1EnvVar(name='CENTAURON_TOKEN', value=token),
            # # TODO token as k8s secret env variable
            V1EnvVar(name='CENTAURON_ADDRESS', value=settings.EXTERNAL_ADDRESS),
            # V1EnvVar(name='STAGE_INSTANCE', value=stage_instance.id_as_str),
            V1EnvVar(name='OUTPUT', value=json.dumps(job.definition.output)),
            *env_vars_sidecar
        ]
    )
    container_computing_tasks = list(filter(lambda e: e.name == 'computing-task', pod_spec.containers))
    if len(container_computing_tasks) == 1:
        if container_computing_tasks[0].volume_mounts == None:
            container_computing_tasks[0].volume_mounts = []
        container_computing_tasks[0].volume_mounts.append(
            V1VolumeMount(mount_path='/output', name=output_tmp_volume_name))
        for vm in computing_task_volume_mounts:
            container_computing_tasks[0].volume_mounts.append(vm)

    if len(container_copy_input) == 1:
        container_copy_input[0].volume_mounts.append(data_volume_mount)

    pod_spec.containers.append(helper_container)
    if pod_spec.volumes == None: pod_spec.volumes = []
    for v in volumes:
        pod_spec.volumes.append(v)

    # set pod name
    meta: V1ObjectMeta = pod.metadata
    meta.name = None
    meta.generate_name = f'{namespace[:min(len(namespace), 252)]}-'

    # never restart in case of failure
    pod_spec.restart_policy = 'Never'

    created_pod = k8s_core_api.create_namespaced_pod(namespace=namespace, body=pod)
    job.set_k8s_pod_name(created_pod.metadata.name)
    logging.info('Job created on k8s.')
    job.status = ComputingJobExecution.Status.CREATED
    job.save(update_fields=['status', 'k8s_data'])


def sanitize_job_name(job_name: str, max=63):
    job_name = job_name.lower().strip().replace(' ', '-')[:min(max, len(job_name))]
    if job_name.endswith('-'):
        job_name = job_name[:len(job_name) - 1]
    return job_name


def test_rfc_1123_compliance(s: str):
    import re
    return re.match('^[a-z0-9]([-a-z0-9]*[a-z0-9])?(\\.[a-z0-9]([-a-z0-9]*[a-z0-9])?)*$', s) is not None


def get_auth_token(profile):
    token, _ = Token.objects.update_or_create(user=profile.user)
    return token.key


@shared_task
def delete_k8s_job(pod_name: str):
    # TODO k8s gave two pods the same name? so just to be sure filter here instead of get.
    jobs = ComputingJobExecution.objects.filter(k8s_data__contains={'pod_name': pod_name})
    for job in jobs:
        pod_name = job.k8s_pod_name
        namespace = job.namespace
        logging.info('Deleting job %s, namespace %s', pod_name, namespace)
        if pod_name is None:
            logging.error('Pod name is None. Exiting.')
            return
        try:
            k8s_core_api.delete_namespaced_pod(namespace=namespace,
                                               name=pod_name)
            job.status = ComputingJobExecution.Status.KILLED
            job.save(update_fields=['status'])
            # send_webhook_for_job_killed.delay(job.id_as_str)
            # send_webhook_for_job_status_changed.delay(job.id_as_str)
        except ApiException as e:
            if e.status == 404:
                logging.error('Pod already deleted')
            else:
                raise e


@shared_task
def export_artifacts(computing_job_pk: str, export_path: str):
    job = ComputingJobExecution.objects.get(pk=computing_job_pk)
    suffix = '.exporting'
    export_path = export_path + suffix
    path = Path(export_path)
    path.mkdir(parents=True)

    for artifact in job.artifacts.all():
        src = artifact.stage_instance.artifact_path / artifact.path
        dst = path / artifact.path
        logging.info('Copy %s to %s.', src, dst)
        shutil.copy(src, dst)

    dst = Path(str(path.absolute())[:len(str(path.absolute())) - len(suffix)])
    logging.info('Renaming %s to %s.', path, dst)
    shutil.move(path, dst)
    logging.info('Exporting artifacts for job %s done.', job.name)


def serialize_to_k8s(obj: Dict[str, Any], resource: str):
    class FakeKubeResponse:
        def __init__(self, obj):
            import json
            self.data = json.dumps(obj)

    fake_kube_response = FakeKubeResponse(obj)
    return k8s_core_api.api_client.deserialize(fake_kube_response, resource)


def get_log_for_container(job: ComputingJobExecution, container: str):
    pod_name = job.k8s_pod_name
    logging.info('Getting log for namespace %s, pod %s, container {}', job.namespace, pod_name, container)
    try:
        log = k8s_core_api.read_namespaced_pod_log(pod_name, container=container, namespace=job.namespace)
        return log
    except ApiException as e:
        if e.status == 404 or e.status == 400:
            logging.info('Pod {} or container not found in namespace {}', pod_name, container, job.namespace)
        else:
            logging.exception(e)
        return None


@shared_task
def cleanup_pod_errors():
    """
    This task should run periodically to delete pods that have errors not captured by the helper container,
    e.g. UnexpectedAdmissionError or error pulling the helper image from the registry.
    Those tasks are queried and then set to error + webhook to inform the application.
    """

    def send_log(job, log, type):
        log = ComputingJobLogEntry.objects.create(job=job, position=0, content=log, type=type, logged_at=timezone.now())

    # only the pending jobs can have one error not captured by the helper container.
    pending_jobs = ComputingJobExecution.objects.filter(status__in=[ComputingJobExecution.Status.CREATED,
                                                                    ComputingJobExecution.Status.CREATING,
                                                                    ComputingJobExecution.Status.RUNNING,
                                                                    ComputingJobExecution.Status.PENDING])
    # print(pending_jobs)

    events_cache = {}  # key: namespace, value: event
    logging.info(f'Total jobs: {pending_jobs.count()}')
    for job in pending_jobs:
        pod_name = job.k8s_pod_name
        namespace = job.definition.namespace
        if pod_name is None:
            continue
        logging.debug(f'Checking pod name {pod_name}')
        try:
            pod = k8s_core_api.read_namespaced_pod(pod_name, namespace=namespace)
        except ApiException as e:
            if e.status == 404:
                job.status = ComputingJobExecution.Status.KILLED
                job.save(update_fields=['status'])
                logging.warning(f'Pod {pod_name} already deleted.')
                continue
            else:
                raise e
        phase = pod.status.phase
        if phase == 'Succeeded':
            continue

        # this error is mystical. Report and delete pod if occurs
        delete_pod = False

        if pod.status.reason == 'Unknown':
            logging.info(f'Pod {pod_name} has status unknown')
            send_log(job, 'Unknown pod status. Killing pod now.', ComputingJobLogEntry.Type.ERROR)
            delete_pod = True

        if pod.status.reason == 'UnexpectedAdmissionError':
            logging.info(f'Pod {pod_name} has UnexpectedAdmissionError')
            # TODO maybe get events or anything that provides some more information what the error actually is.
            send_log(job, 'UnexpectedAdmissionError. Killing pod now.', ComputingJobLogEntry.Type.ERROR)
            delete_pod = True

        # TODO catch init error for cloning repository

        # volume could not be mounted. report and delete.
        if phase == 'Pending':
            # check in events if a volume can not be mounted
            if namespace not in events_cache:
                events_cache[namespace] = k8s_core_api.list_namespaced_event(namespace=namespace)

            events_filtered = list(
                filter(lambda e: e.involved_object.name == pod_name, events_cache[namespace].items))
            for e in events_filtered:
                if e.reason == 'FailedMount':
                    logging.info(f'Pod {pod_name} has FailedMount: {e.message}')
                    send_log(job, e.message, ComputingJobLogEntry.Type.ERROR)
                    delete_pod = True

        if delete_pod:
            job.finished_at = timezone.now()
            job.save(update_fields=['finished_at'])
            delete_k8s_job.delay(pod_name)

    # also control running jobs
