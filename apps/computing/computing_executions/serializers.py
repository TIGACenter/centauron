from rest_framework.relations import StringRelatedField

from apps.computing.computing_executions.models import ComputingJobExecution
from apps.core.serializers import DynamicFieldsModelSerializer, IdentifierField


class ComputingJobExecutionSerializer(DynamicFieldsModelSerializer):
    identifier = StringRelatedField()
    definition = IdentifierField(read_only=True)

    class Meta:
        model = ComputingJobExecution
        fields = ('definition',
                  'identifier',
                  'status',
                  'batch_number',
                  'started_at',
                  'finished_at',
                  )
