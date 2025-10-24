from rest_framework.relations import StringRelatedField

from apps.challenge.challenge_targetmetric.models import TargetMetric
from apps.core.serializers import DynamicFieldsModelSerializer, IdentifierField


class TargetMetricSerializer(DynamicFieldsModelSerializer):
    identifier = StringRelatedField()
    challenge = IdentifierField(read_only=True)

    class Meta:
        model = TargetMetric
        fields = ('key', 'identifier', 'sort', 'challenge',)
