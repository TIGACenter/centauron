import csv
import logging
import uuid
from io import StringIO

from django.conf import settings
from django.db import connection
from django.utils import timezone
import logging
from rest_framework import status, serializers, mixins, viewsets
from rest_framework.generics import get_object_or_404
from rest_framework.parsers import MultiPartParser, JSONParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.computing.computing_executions.models import ComputingJobExecution
from apps.core import identifier
from apps.core.serializers import IdentifierField
from apps.storage.models import File
from apps.utils import get_node_origin, get_user_node


class FileSerializer(serializers.Serializer):
    name = serializers.CharField()
    original_path = serializers.CharField()
    content_type = serializers.CharField(required=False)
    size = serializers.IntegerField()  # TODO is bigint allowed?
    src = IdentifierField(required=False)


'''
API endpoints to register a new file.
'''


class CreateFileAPI(APIView):
    parser_classes = [MultiPartParser, JSONParser]

    def post(self, request):
        logging.info('Register files request.')
        csv_file = request.FILES.get('file', None)
        if csv_file is None:
            csv_file = get_object_or_404(ComputingJobExecution, pk=request.data.get('job')).get_tmp_dir()
            csv_file /= request.data.get('file')
        else:
            csv_file = csv_file.temporary_file_path()
        with open(csv_file) as f:
            reader = csv.DictReader(f)
            files = [r for r in reader]
        logging.info(files)
        # files_json = json.dumps(files)
        data = FileSerializer(data=files, many=True)
        data.is_valid(raise_exception=True)

        return_identifiers = request.GET.get('return', 'identifiers') == 'identifiers'
        data = data.validated_data
        src_files = {}
        flush_interval = 50_000  # 50_000
        R = []

        with StringIO() as memory_file:
            writer = csv.writer(memory_file)
            csv_header = ['id', 'name', 'content_type', 'case_id', 'created_by_id', 'identifier', 'origin_id',
                          'originating_from_id', 'original_filename', 'original_path', 'size', 'date_created',
                          'last_modified', 'imported']
            writer.writerow(csv_header)
            total = len(data)
            created_by = request.user.profile
            created_by_id = created_by.id_as_str
            now = str(timezone.now().isoformat())
            origin = request.user.profile

            for idx, file in enumerate(data):
                # print(idx)
                if idx > 0:
                    if idx % flush_interval == 0:
                        logging.debug('%s/%s imported.', idx, total)

                name = file.get('name')
                original_path = file.get('original_path')
                size = int(file.get('size', -1))
                content_type = file.get('content_type', None)
                src_file_identifier = file.get('src', None)
                src_file = None

                # retrieve or write into cache
                if src_file_identifier is not None and len(src_file_identifier.strip()) > 0 and str(src_file_identifier) not in src_files:
                    src_files[str(src_file_identifier)] = File.objects.get_by_identifier(src_file_identifier)

                if src_file_identifier is not None and str(src_file_identifier) in src_files:
                    src_file = src_files[str(src_file_identifier)]

                # TODO check if file already exists?!
                # TODO maybe also add the file hash to be sure that the content is the same
                # TODO what if the same slide is used in multiple studies etc. of the same user?
                # qs_file_exists = File.objects.filter(created_by_id=created_by_id, size=size, name=name, original_path=original_path)
                # if not qs_file_exists.exists():
                id = identifier.create_random('file')
                pk = uuid.uuid4()
                writer.writerow(
                    [pk, name, content_type, 'null' if src_file is None else str(src_file.case_id), created_by_id, id,
                     origin.id_as_str,
                     'null' if src_file is None else src_file.id_as_str, name, original_path, size, now, now, False])
                # else:
                #     pk = qs_file_exists.first().pk
                R.append(str(pk))

            logging.info('Adding %s files.', len(R))
            memory_file.seek(0)
            with connection.cursor() as cursor:
                cursor.copy_expert(f'copy storage_file({",".join(csv_header)}) from stdin csv header NULL as \'null\'',
                                   memory_file)
            memory_file.close()
            logging.info('Adding done.')

            # TODO stream the response as a list of file ids
            if not return_identifiers:
                tmpfile = settings.TMP_DIR / f'{uuid.uuid4()}'
                with tmpfile.open('w') as f:
                    f.write("\n".join(R))
            R = R if return_identifiers else str(tmpfile.relative_to(settings.TMP_DIR))
            return Response(status=status.HTTP_201_CREATED, data=R)

