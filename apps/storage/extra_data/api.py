import logging

import loguru
from rest_framework import mixins, viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.identifier import create_random
from apps.storage.extra_data.models import ExtraData
from apps.storage.extra_data.permissions import IsUserAnnotationBackend
from apps.storage.extra_data.serializers import ExtraDataSerializer
from apps.storage.models import File
from apps.utils import get_node_origin


class CreateExtraDataForAnnotationBackendViewSet(mixins.CreateModelMixin, viewsets.GenericViewSet):
    serializer_class = ExtraDataSerializer
    permission_classes = [IsAuthenticated, IsUserAnnotationBackend]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        event = serializer.validated_data.pop('event')

        try:
            for e in serializer.validated_data.get('payload', []):
                if event == 'annotation_created':
                    self.create_annotation(e)
                if event == 'annotation_deleted':
                    self.delete_annotation(e)
            # file_identifier = serializer.validated_data['payload']['task']['extra_data']['id']
        except Exception as e:
            logging.exception(e)
            return Response(status=400)

        # file = File.objects.filter(identifier=file_identifier)
        # if not file.exists():
        #     loguru.logging.warning(f'file with identifier [{file_identifier}] does not exist.')
        #     return Response(status=400)
        #
        # kw = dict(created_by=self.request.user.profile,
        #           origin=get_node_origin(),
        #           data=serializer.validated_data.pop('payload'),
        #           identifier=create_random('extra-data'),
        #           file=file.get())
        #     self.perform_create(serializer, **kw)
        # if event == 'annotation_deleted':
        #     # TODO delete extra data
        #     pass

        return Response(status=status.HTTP_200_OK)

    def perform_create(self, serializer, **kwargs):
        serializer.save(**kwargs)

    def create_annotation(self, event):
        file_identifier = event['task']['extra_data']['id']
        file = File.objects.filter(identifier=file_identifier)
        if not file.exists():
            logging.warning(f'file with identifier [{file_identifier}] does not exist.')
            raise ValueError(f'file with identifier [{file_identifier}] does not exist.')
        user = self.request.user.profile
        kw = dict(created_by=user,
                  origin=user,
                  identifier=create_random('extra-data'),
                  application_identifier=user.identifier,
                  file=file.get(),
                  data=event)

        ExtraData.objects.create(**kw)

    def delete_annotation(self, event):
        file_identifier = event['task']['extra_data']['id']
        file = File.objects.filter(identifier=file_identifier)
        if not file.exists():
            raise ValueError(f'file with identifier {file_identifier} not found')
        file.first().extra_data.filter(data=event).delete()
