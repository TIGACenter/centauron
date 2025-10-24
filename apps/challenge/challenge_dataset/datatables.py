from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from rest_framework import serializers as rf_serializers
from rest_framework import viewsets

from apps.challenge.challenge_dataset import serializers
from apps.challenge.challenge_dataset.models import Dataset
from apps.storage.models import File


class DatasetDataTableView(LoginRequiredMixin, viewsets.ModelViewSet):
    serializer_class = serializers.DatasetDataTableSerializer

    def get_queryset(self):
        return Dataset.objects.filter(challenge_id=self.kwargs.get('pk'))

    def destroy(self, request, *args, **kwargs):
        return HttpResponse(status=400)

    def retrieve(self, request, *args, **kwargs):
        return HttpResponse(status=400)

    def create(self, request, **kwargs):
        return self.list(request, **kwargs)


class FileSerializerWithOrigin(serializers.FileSerializer):
    origin = rf_serializers.SerializerMethodField()

    class Meta(serializers.FileSerializer.Meta):
        pass

    def get_origin(self, obj: File) -> str:
        return obj.origin.display


class FileDataTableView(LoginRequiredMixin, viewsets.ModelViewSet):
    serializer_class = FileSerializerWithOrigin

    def get_queryset(self):
        objects_filter = File.objects.filter(datasets__id__in=[self.kwargs.get('dataset_pk', None)]).prefetch_related(
            'origin')
        return objects_filter

    def destroy(self, request, *args, **kwargs):
        return HttpResponse(status=400)

    def retrieve(self, request, *args, **kwargs):
        return HttpResponse(status=400)

    def create(self, request, **kwargs):
        return self.list(request, **kwargs)
