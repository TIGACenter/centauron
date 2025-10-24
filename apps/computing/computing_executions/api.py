import csv
import io
import logging
import uuid

from django.db import transaction, connection
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.utils.decorators import method_decorator
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.computing.computing_executions.models import ComputingJobExecution
from apps.computing.computing_log.models import ComputingJobLogEntry
from apps.computing.computing_log.tasks import persist_log
from apps.computing.tasks import start_stage_from_last
from apps.core import identifier
from apps.storage.storage_importer.tasks import import_computing_job_artefacts


class BaseAPIView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]


class StageView(BaseAPIView):

    def post(self, request, pk):
        logging.info('Receiving new status from job.')
        data = request.data
        state = data.get('status')
        node = data.get('node', None)

        job = ComputingJobExecution.objects.get(pk=pk)
        job.status = ComputingJobExecution.Status[state.upper()]

        if node is not None:
            job.k8s_data['node'] = node

        if job.status == ComputingJobExecution.Status.SUCCESS:
            if job.started_at is None:
                job.started_at = timezone.now()
            job.finished_at = timezone.now()

        if job.status == ComputingJobExecution.Status.PREPARING:
            job.started_at = timezone.now()

        job.save()

        additional_data = None
        if node is not None:
            additional_data = dict(k8s_node=node, k8s_pod_name=job.k8s_pod_name)
            job.k8s_data = {**job.k8s_data, **additional_data}
            job.save(update_fields=['k8s_data'])

        if job.status == ComputingJobExecution.Status.SUCCESS:
            start_stage_from_last.delay(job.id_as_str)

        return HttpResponse(status=200)


class LogView(BaseAPIView):

    def post(self, request, pk):
        logging.debug('Adding new log from stage.')
        data = request.data
        log = data['line']
        position = data['position']
        type = data.get('type', 'output')
        persist_log.delay(pk, log, position, type)
         # tasks.send_webhook_for_log_added.delay(log.id_as_str)  # .delay
        return HttpResponse(status=200)


@method_decorator(transaction.non_atomic_requests, name='dispatch')
class ArtifactView(BaseAPIView):
    # parser_classes = [MultiPartParser]

    def post(self, request, pk):
        logging.info('Adding new artifacts from stage.')
        data = request.data
        files = data # data.get('file', None)

        if files is None:
            logging.error('No artifact file provided.')
            return Response(status=status.HTTP_400_BAD_REQUEST)

        if not isinstance(files, list):
            files = [files]
        # else:
        # files = [e.strip() for e in file if len(e.strip()) > 0]

        # created_by = self.request.user.profile
        origin_id = request.user.profile.id_as_str

        job = ComputingJobExecution.objects.get(pk=pk)
        # params = {k: request.GET.get(k) for k in request.GET}
        job_id = job.id_as_str
        computing_results_memory_file = io.StringIO()
        computing_results_writer = csv.writer(computing_results_memory_file)
        computing_results_csv_header = ['id', 'date_created', 'last_modified', 'identifier', 'origin_id']
        computing_results_writer.writerow(computing_results_csv_header)

        computing_artifact_memory_file = io.StringIO()
        computing_artifact_writer = csv.writer(computing_artifact_memory_file)
        computing_artifact_csv_header = ['computingjobresult_ptr_id', 'computing_job_id', 'file_id']
        computing_artifact_writer.writerow(computing_artifact_csv_header)

        now = timezone.now().isoformat()

        # TODO i think the following was done to register a large number of files = tilesets. one file with the paths of all files is registered and then here all files references in that file are registered as well.
        # TODO find a better solution for that.
        # for tmp_file in file:
        #     tmp_file = job.artifact_path / tmp_file
        #     if not tmp_file.exists():
        #         tmp_file = settings.TMP_DIR / tmp_file
        #     if not tmp_file.exists():
        #         logging.error('File not found. Searched in [%s, %s]', job.artifact_path, settings.TMP_DIR)
        #         return Response(status=400)
        #     with tmp_file.open() as f:
        #         files = f.readlines()
        #         files = list(map(lambda e: e.strip(), files))
        #     # delete tmp file as not needed anymore.
        #     tmp_file.unlink()

        for f in files:
            # created_file = File.objects.create(
            #     created_by=get_user_node(),
            #     origin_id=origin_id,
            #     original_filename=f.get('original_filename'),
            #     original_path=f.get('original_path'),
            #     name=f.get('file')
            # )
            artifact_id = str(uuid.uuid4())
            computing_results_writer.writerow(
                [artifact_id, now, now, identifier.create_random('artefact'), origin_id])
            computing_artifact_writer.writerow([artifact_id, job_id, f])
        try:
            with connection.cursor() as cursor:
                computing_results_memory_file.seek(0)
                cursor.copy_expert(
                    f'copy computing_artifact_computingjobresult({",".join(computing_results_csv_header)}) from stdin csv header',
                    computing_results_memory_file
                )
                computing_artifact_memory_file.seek(0)
                cursor.copy_expert(
                    f'copy computing_artifact_computingjobartifact({",".join(computing_artifact_csv_header)}) from stdin csv header',

                    computing_artifact_memory_file
                )
        except Exception as e:
            raise e
        finally:
            computing_results_memory_file.close()
            computing_artifact_memory_file.close()

        # start importer
        import_computing_job_artefacts.delay(job.id_as_str)

        # # files are already registered. now create artefacts.
        # """
        # 1. insert files
        # 2. insert computing artifacts
        # 3.
        # """
        # for f in data:
        #     original_path = f['original_path']
        #     path = f['path']
        #     size = f['size']
        #     original_file_name = f['original_file_name']
        #     parent_id = f.get('parent', None)
        #     parent = {}
        #     if parent_id is not None:
        #         parent['parent'] = ComputingJobExecution.objects.get(pk=parent_id)
        #
        #     if not ComputingJobArtifact.objects.filter(computing_job=job,
        #                                                file__original_path=original_path,
        #                                                file__original_filename=original_file_name).exists():
        #         # import file with importer to get the file identifier
        #         # create file first
        #         # TODO add additional parameters like fileset or sth.
        #         # TODO import data with csv copy command again.
        #
        #         qs = File.objects.filter(name=original_file_name, size=size, origin=created_by, imported=False,
        #                                  **params)
        #         if not qs.exists():
        #             file = File.objects.create(
        #                 name=original_file_name,
        #                 identifier=identifier.create_random('file'),
        #                 origin=created_by,
        #                 size=size,
        #                 original_filename=original_file_name,
        #                 original_path=path
        #             )
        #         else:
        #             file = qs.first()
        #         # then call importer
        #         # TODO import all files at once
        #         qs_file = import_single_file(file, settings.COMPUTING_ARTIFACT_DIRECTORY / job.id_as_str / path,
        #                                      from_celery=False, remove_src_folder=False)
        #
        #         artifact = ComputingJobArtifact.objects.create(computing_job=job,
        #                                                        file=qs_file.first(),
        #                                                        identifier=identifier.create_random('artefact'),
        #                                                        origin=created_by,
        #                                                        **parent)  # TODO set origin here to what?
        #
        # # TODO execute copy from cmd and close io buffers

        return JsonResponse(status=200, data={})  # , data={'artifact_id': artifact.id_as_str})
        # return JsonResponse(status=400, data={})
