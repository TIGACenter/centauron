from rest_framework import serializers
from rest_framework.relations import StringRelatedField

from apps.computing.computing_log.models import ComputingJobLogEntry
from apps.core.serializers import DynamicFieldsModelSerializer, IdentifierField


class ComputingJobLogEntrySerializer(DynamicFieldsModelSerializer):
    content = serializers.SerializerMethodField()
    identifier = StringRelatedField()
    computing_job = IdentifierField(read_only=True)

    class Meta:
        model = ComputingJobLogEntry
        fields = ('type', 'position', 'logged_at', 'content', 'identifier', 'computing_job', )

    def get_content(self, o: ComputingJobLogEntry):
        return o.content if not o.submission_log_entry.obscure else '[obscured]'
