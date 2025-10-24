import logging
import os
import shutil

from django.http import JsonResponse
import logging

from apps.computing.computing_artifact.models import ComputingJobArtifact
from apps.computing.computing_executions.api import BaseAPIView
from apps.computing.computing_executions.models import ComputingJobExecution


class ArtifactView(BaseAPIView):

    def post(self, request, pk):
        logging.info('Adding new artifact from stage.')
        data = request.data
        original_path = data['original_path']
        path = data['path']
        original_file_name = data['original_file_name']
        folder = data.get('folder', False)
        parent_id = data.get('parent', None)

        parent = {}
        if parent_id is not None:
            parent['parent'] = ComputingJobExecution.objects.get(pk=parent_id)
        job = ComputingJobExecution.objects.get(pk=pk)
        if not ComputingJobArtifact.objects.filter(job=job,
                                       original_path=original_path,
                                       original_file_name=original_file_name,
                                       path=path,
                                       folder=folder).exists():
            artifact = ComputingJobArtifact.objects.create(job=job,
                                               original_path=original_path,
                                               original_file_name=original_file_name,
                                               path=path,
                                               folder=folder,
                                               **parent)
            # TODO
            # file_identifiers = send_file_to_storage_service(artifact)
            # if file_identifiers is not None:
            #     path_ = artifact.file_path
            #     if path_.exists():
            #         logging.debug('Deleting original file @ {}', artifact.file_path)
            #         if folder:
            #             shutil.rmtree(artifact.file_path)
            #         else:
            #             os.unlink(artifact.file_path)
            # artifact.file_identifier = file_identifiers
            # artifact.save(update_fields=['file_identifier'])

            # tasks.send_webhook_for_job_artifact_added.delay(artifact.id_as_str)

            return JsonResponse(status=200, data={'artifact_id': artifact.id_as_str})
        return JsonResponse(status=400, data={})

