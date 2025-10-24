from rest_framework.relations import StringRelatedField

from apps.computing.computing_artifact.models import ComputingJobArtifact
from apps.core.serializers import DynamicFieldsModelSerializer, IdentifierField


class ComputingJobArtefactSerializer(DynamicFieldsModelSerializer):
    identifier = StringRelatedField()
    computing_job = IdentifierField(read_only=True)
    file = IdentifierField(read_only=True)

    class Meta:
        model = ComputingJobArtifact
        fields = ('computing_job', 'file', 'identifier', 'date_created',)
