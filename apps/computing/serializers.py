from rest_framework.fields import SerializerMethodField
from rest_framework.relations import StringRelatedField

from apps.computing.models import ComputingJobDefinition, ComputingPipeline, ComputingJobTemplate
from apps.core.serializers import IdentifierField, DynamicFieldsModelSerializer


class ComputingJobTemplateSerializer(DynamicFieldsModelSerializer):
    origin = IdentifierField(read_only=True)
    identifier = StringRelatedField()

    class Meta:
        model = ComputingJobTemplate
        fields = ('template_fields', 'origin', 'identifier')


class ComputingJobDefinitionSerializer(DynamicFieldsModelSerializer):
    identifier = StringRelatedField()
    template = ComputingJobTemplateSerializer()
    origin = IdentifierField(read_only=True)
    submission = SerializerMethodField()

    class Meta:
        model = ComputingJobDefinition
        fields = ('identifier', 'type', 'origin', 'name',
                  'docker_image', 'entrypoint', 'template', 'submission',
                  'total_batches', 'batch_size','execution_type', 'input', 'position', 'output')

    def get_submission(self, o: ComputingJobDefinition):
        return str(o.pipeline.submission.identifier)


class ComputingPipelineSerializer(DynamicFieldsModelSerializer):
    stages = ComputingJobDefinitionSerializer(many=True,
                                              fields=['name', 'template', 'identifier', 'origin'])
    origin = IdentifierField(read_only=True)
    identifier = StringRelatedField()
    challenge = IdentifierField(read_only=True)

    class Meta:
        model = ComputingPipeline
        fields = ('identifier', 'origin', 'stages', 'challenge')



class ComputingPipelineFullSerializer(ComputingPipelineSerializer):
    stages = ComputingJobDefinitionSerializer(many=True,
                                              fields=['name', 'template',
                                                      'position',
                                                      'credentials',
                                                      'identifier', 'origin', 'entrypoint', 'namespace', 'docker_image',
                                                      'input', 'output', 'execution_type'])

    class Meta:
        model = ComputingPipelineSerializer.Meta.model
        fields = ComputingPipelineSerializer.Meta.fields
