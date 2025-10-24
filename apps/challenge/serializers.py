from rest_framework.relations import StringRelatedField

from apps.challenge.models import Challenge
from apps.computing.serializers import ComputingPipelineSerializer
from apps.core.serializers import IdentifierField, DynamicFieldsModelSerializer, AnnotationSerializer


class ChallengeSerializer(DynamicFieldsModelSerializer):
    identifier = StringRelatedField()
    origin = IdentifierField(read_only=True)
    pipeline = ComputingPipelineSerializer()
    annotations = AnnotationSerializer(many=True)

    class Meta:
        model = Challenge
        fields = ('pipeline', 'identifier', 'origin', 'name', 'open_from', 'open_until', 'description', 'dataset_name', 'tags', 'annotations')

