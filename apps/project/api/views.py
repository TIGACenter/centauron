from rest_framework import mixins, viewsets

from apps.project.api.serializers import ProjectSerializer
from apps.project.models import Project


class ProjectViewSet(mixins.RetrieveModelMixin,
                     mixins.CreateModelMixin,
                     viewsets.GenericViewSet):
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user.profile)
