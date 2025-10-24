from rest_framework import serializers

from apps.node.models import Node
from apps.project.models import Project


class ProjectSerializer(serializers.ModelSerializer):
    origin = serializers.SlugRelatedField(slug_field='identifier', queryset=Node.objects.all())
    id = serializers.UUIDField(read_only=True)
    identifier = serializers.CharField(required=True)

    class Meta:
        model = Project
        fields = ('name', 'id', 'identifier', 'origin')
