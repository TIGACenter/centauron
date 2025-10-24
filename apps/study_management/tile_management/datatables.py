from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from rest_framework.viewsets import ModelViewSet

from apps.study_management.tile_management import serializers
from apps.study_management.tile_management.models import TileSet


class TileSetFilesViewSet(LoginRequiredMixin, ModelViewSet):
    serializer_class = serializers.TileSetFileTableSerializer

    def get_queryset(self):
        ts = TileSet.objects.get(created_by=self.request.user.profile, pk=self.request.GET.get('tileset_pk'))
        return ts.files.all().prefetch_related('codes', 'annotations', 'projects', 'case', 'origin', 'originating_from')

    def destroy(self, request, *args, **kwargs):
        return HttpResponse(status=400)

    def retrieve(self, request, *args, **kwargs):
        return HttpResponse(status=400)

    def create(self, request, **kwargs):
        return self.list(request, **kwargs)





