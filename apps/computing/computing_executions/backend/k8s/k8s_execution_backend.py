from pathlib import Path

import kubernetes
from django.conf import settings
from kubernetes.client import V1Pod, V1ObjectMeta, V1PodSpec, V1LocalObjectReference, V1Container, V1Volume, \
    V1VolumeMount, V1EmptyDirVolumeSource, V1ResourceRequirements, V1EnvVar

from apps.computing.computing_executions.backend.adapter import BaseAdapter
from apps.computing.computing_executions.backend.k8s.tasks import start_job
from apps.computing.computing_executions.models import ComputingJobExecution
from apps.computing.models import ComputingJobDefinition

# we only need this for model serialization to json
k8s_core_api = kubernetes.client.CoreV1Api()


class K8SExecutionBackend(BaseAdapter):

    def execute(self, job: ComputingJobExecution):
        start_job(job.id_as_str)

    def prepare(self, job: ComputingJobExecution):
        # create k8s spec
        spec = self.create_k8s_spec(job)
        job.definition.k8s_spec = k8s_core_api.api_client.sanitize_for_serialization(spec)
        job.definition.save()

    def create_k8s_spec(self, job: ComputingJobExecution):
        # k8s_container_kwargs = {}
        # if len(job.definition.entrypoint) > 0:
        #     cmd = []
        #     for i, s in enumerate(job.definition.entrypoint):
        #         if i > 0:
        #             cmd += ['&&']
        #         cmd += [s]
        #     k8s_container_kwargs['command'] = ['/bin/sh']
        #     k8s_container_kwargs['args'] = ['-c'] + [' '.join(cmd)]
        # init_containers = []
        # volumes = []
        # computing_task_volumes = []
        # if job.definition.is_validation_job:
        #     input_volume_name = 'input'
        #     input_volume = V1Volume(name=input_volume_name, empty_dir=V1EmptyDirVolumeSource())
        #     input_volume_mount = V1VolumeMount(mount_path=f'/input', name=input_volume_name)
        #     volumes.append(input_volume)
        #     computing_task_volumes.append(input_volume_mount)
        #     copy_cmd = []
        #     # TODO enable patterns?
        #     # artifacts_filter = job.training_job.artifacts.all()
        #     # identifiers = [*artifacts_filter.values_list('file_identifier', flat=True)]
        #     # response = requests.post(settings.CENTAURON_STORAGE_SERVICE + 'files/path/',
        #     #                          json={'identifier': identifiers},
        #     #                          headers={'Authorization': f'Bearer {get_service_account_jwt()}'})
        #     # response.raise_for_status()
        #     # TODO how to copy in files??
        #     # for f in response.json():
        #     #     file = Path(f['path'])
        #     #     src = Path('/data') / file
        #     #     dest = Path('/input') / f['original_filename']
        #     #
        #     #     copy_cmd.append(
        #     #         f'mkdir -p {dest.parent}')  # create parent dir if not exist yet to ensure cp command runs properly
        #     #     copy_cmd.append(f'cp -r {src} {dest}')
        #     #
        #     # init_containers.append(V1Container(
        #     #     name='copy-input',
        #     #     image='busybox:1.36.0',
        #     #     command=['/bin/sh'],
        #     #     args=['-c', ' && '.join(copy_cmd)],
        #     #     volume_mounts=[input_volume_mount],
        #     # ))
        #
        # return V1Pod(
        #     metadata=V1ObjectMeta(name=''),
        #     spec=V1PodSpec(
        #         image_pull_secrets=[V1LocalObjectReference(name=settings.PRIVATE_DOCKER_REGISTRY_K8S_SECRET_NAME)],
        #         init_containers=[*init_containers],
        #         containers=[
        #             V1Container(name='computing-task',
        #                         image=job.definition.retagged_docker_image,
        #                         volume_mounts=[*computing_task_volumes],
        #                         **k8s_container_kwargs
        #                         )
        #         ],
        #         restart_policy='Never',
        #         volumes=[*volumes]  # input and output volumes will be added by the computing service
        #     )
        # )

        k8s_container_kwargs = dict(image=job.definition.retagged_docker_image)
        # repo_volume_mount_path = '/repo'

        # only use a script if provided. if not use the docker container entry point
        entrypoint = job.definition.entrypoint if isinstance(job.definition.entrypoint, list) else [
            job.definition.entrypoint]
        if len(entrypoint) > 0:
            cmd = []
            for i, s in enumerate(entrypoint):
                if i > 0:
                    cmd += ['&&']
                cmd += [s]
            k8s_container_kwargs['command'] = ['/bin/sh']
            args = []
            if job.definition.args is not None:
                args = [f'--{k} {v}' for k, v in job.definition.args.items()]
            k8s_container_kwargs['args'] = ['-c'] + [' '.join(cmd + args)]

        if job.definition.resources is not None:
            k8s_container_kwargs['resources'] = V1ResourceRequirements(
                **job.definition.resources)  # resources is a dict

        # repo_volume_mount_name = 'git-cache'
        # repo_volume_mount = V1VolumeMount(
        #     mount_path=repo_volume_mount_path,
        #     name=repo_volume_mount_name
        # )
        # command_git_clone = ['git',
        #                      'clone',
        #                      '--no-checkout',
        #                      '--',
        #                      stage_instance.definition.computing_job.git_repository,
        #                      repo_volume_mount_path,
        #                      '&&',
        #                      f'cd {repo_volume_mount_path}',
        #                      '&&',
        #                      'git',
        #                      'checkout',
        #                      stage_instance.definition.computing_job.git_commit]
        # specify a initcontainer that runs before the normal container and clones the git repo + stores it in a volume
        # for use by the real container

        # create hostpath volumes read only for input files
        # one volume per file is very slow for large amount of files so go with readonly directory mount
        # only add volume to data if it is requested.
        # TODO k8s nodes need to have the host directory mounted under the same path
        computing_task_volumes = []
        volumes = []
        init_containers = []

        if job.definition.has_input:
            input_volume_name = 'input'
            input_volume = V1Volume(name=input_volume_name, empty_dir=V1EmptyDirVolumeSource())
            input_volume_mount = V1VolumeMount(mount_path=f'/input', name=input_volume_name)
            volumes.append(input_volume)
            computing_task_volumes.append(input_volume_mount)
            copy_cmd = []
            # input is a list of e.g. ['predict:result.csv', 'predict:*']
            for stage_pattern in job.definition.input:
                stage, pattern = stage_pattern.split(':')
                if pattern == '*':
                    pattern = '(.*?)'
                # get other stages of
                # exec_batches = list(filter(lambda e: e.executions.filter(status=ComputingJobExecution.Status.SUCCESS), job.definition.pipeline.stages.filter(name=stage)))[0] #.distinct()
                stage_with_artifact = job.definition.pipeline.stages.filter(name=stage).first()
                defs = ComputingJobDefinition.objects.filter(pipeline=job.definition.pipeline, name=stage)
                # number_of_batches = 0 if stage_with_artifact.is_batched else
                # is_batched = number_of_batches > 1
                is_batched = stage_with_artifact.is_batched
                for idx, exec in enumerate(stage_with_artifact.executions.all()):
                    artifacts_filter = exec.artifacts.filter(file__name__iregex=pattern)
                    for f in artifacts_filter:
                        file = settings.COMPUTING_K8S_DATA_DIRECTORY / f.file.path
                        src = Path('/data') / (file.relative_to(settings.COMPUTING_K8S_DATA_DIRECTORY))
                        dest = Path('/input')
                        if is_batched:
                            dest /= str(idx)
                        dest /= f.file.original_path

                        copy_cmd.append(
                            f'mkdir -p {dest.parent}')  # create parent dir if not exist yet to ensure cp command runs properly
                        copy_cmd.append(f"cp -r '{src}' '{dest}'")

            #     computing_task_volumes.append(input_volume_mount)
            # iterate over input patterns
            # get files from db that contain pattern
            # get stage def. if batched get batched stage instances
            # copy files in this pattern /input/<batch>/file.csv

            init_containers.append(V1Container(
                name='copy-input',
                image='busybox:1.36.0',
                command=['/bin/sh'],
                args=['-c', ' && '.join(copy_cmd)],
                volume_mounts=[input_volume_mount],
            ))
        repo_volume_mount_path = ''
        env = [V1EnvVar(name=key, value=value) for key, value in job.definition.environment_variables.items()]
        env.append(V1EnvVar(name='JOB_PK', value=job.id_as_str))
        env.append(V1EnvVar(name='NODE_IDENTIFIER', value=settings.IDENTIFIER))

        return V1Pod(metadata=V1ObjectMeta(name=''),
                     spec=V1PodSpec(
                         image_pull_secrets=[
                             V1LocalObjectReference(name=settings.PRIVATE_DOCKER_REGISTRY_K8S_SECRET_NAME)],
                         # metadata=
                         init_containers=[
                             # V1Container(
                             #     name='git-clone',
                             #     image='alpine/git',
                             #     command=['/bin/sh'],
                             #     args=['-c', ' '.join(command_git_clone)],
                             #     volume_mounts=[repo_volume_mount],
                             #     env=[V1EnvVar(
                             #         name='GIT_DISCOVERY_ACROSS_FILESYSTEM',
                             #         value='1'
                             #     )]
                             # ),
                             *init_containers
                         ],
                         containers=[
                             V1Container(
                                 name='computing-task',
                                 env=env,
                                 working_dir=repo_volume_mount_path,
                                 volume_mounts=[  # repo_volume_mount,
                                     *computing_task_volumes],
                                 **k8s_container_kwargs
                             )
                         ],
                         restart_policy="Never",
                         volumes=[
                             # V1Volume(
                             #     name=repo_volume_mount_name,
                             #     empty_dir=V1EmptyDirVolumeSource()
                             # ),
                             *volumes
                         ]
                     ))
