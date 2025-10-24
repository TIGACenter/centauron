import csv
import io

from django.conf import settings
from django.db import connection, transaction
from django.http import JsonResponse
from django.utils.decorators import method_decorator
import logging
from rest_framework import status, serializers
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.serializers import IdentifierField
from apps.storage.models import File
from apps.study_management.models import Study
from apps.study_management.tile_management.models import TileSet


class AddFileToTileSetSerializer(serializers.Serializer):
    # files = IdentifierField(many=True)
    files = serializers.ListField(
        child=IdentifierField(),
        required=False
    )
    file = serializers.CharField(required=False)

@method_decorator(transaction.non_atomic_requests, name='dispatch')
class AddFileToTileSet(APIView):

    def post(self, request, **kwargs):
        logging.info('Add files to tileset request.')
        ser = AddFileToTileSetSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        files = data.get('files', None)
        file = data.get('file', None)
        if files is None and file is None:
            logging.error('Files and file not given.')
            return Response(status=status.HTTP_400_BAD_REQUEST)

        created_by = self.request.user.profile
        study = get_object_or_404(Study, pk=kwargs.get('pk'), created_by=created_by)
        tileset = get_object_or_404(TileSet, pk=kwargs.get('tileset_pk'),
                                    created_by=created_by)  # TODO add study to query

        if file is not None:
            tmp_file = settings.TMP_DIR / file
            if not tmp_file.exists():
                logging.error('tmp file %s does not exist.', tmp_file)
                return Response(status=status.HTTP_400_BAD_REQUEST)

            with tmp_file.open() as f:
                files = f.readlines()
                files = list(map(lambda e: e.strip(), files))

        memory_file = io.StringIO()
        writer = csv.writer(memory_file)
        csv_header = ['fileset_id', 'file_id']
        writer.writerow(csv_header)
        # with transaction.atomic():
            # qs = File.objects.filter(id__in=files, created_by=created_by).values_list('pk', flat=True)
        writer.writerows([[tileset.id_as_str, str(f)] for f in files])
        memory_file.seek(0)
        # with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.copy_expert(
                f'copy fileset_fileset_files({",".join(csv_header)}) from stdin csv header', memory_file
            )
            # cursor.commit()
        memory_file.close()
        logging.info('Done adding tiles to tileset.')
        return Response(status=status.HTTP_200_OK)
