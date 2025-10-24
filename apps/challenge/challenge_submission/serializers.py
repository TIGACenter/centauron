from rest_framework import serializers
from rest_framework.relations import StringRelatedField

from apps.challenge.challenge_dataset.models import EvaluationCode
from apps.challenge.challenge_submission.models import Submission, TargetMetricValue
from apps.challenge.models import Challenge
from apps.core.serializers import IdentifierField, DynamicFieldsModelSerializer
from apps.project.project_ground_truth.models import GroundTruthSchema
from apps.user.user_profile.models import Profile


#
# class DatasetSerializer(DynamicFieldsModelSerializer):
#     identifier = StringRelatedField()
#     challenge = IdentifierField(read_only=True)
#     origin = IdentifierField(read_only=True)
#
#     class Meta:
#         model = Dataset
#         fields = ('identifier', 'origin', 'challenge', 'name', 'type', 'description')

class SubmitterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = ('identifier', 'human_readable')

    identifier = serializers.CharField()
    human_readable = serializers.CharField()


class SubmissionSerializer(serializers.ModelSerializer):
    identifier = StringRelatedField()
    submitter = SubmitterSerializer(read_only=True)
    computing_pipeline = IdentifierField(read_only=True)
    challenge = IdentifierField(read_only=True)

    # fields = serializers.JSONField()

    class Meta:
        model = Submission
        fields = ('identifier', 'submitter', 'date_created', 'challenge', 'name', 'fields', 'computing_pipeline')

    # def get_submitter(self, obj:Submission):
    #     return IdentifierField().to_representation(obj.created_by)


class SubmissionDataTableSerializer(serializers.ModelSerializer):
    href = serializers.SerializerMethodField()
    created_by = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()

    class Meta:
        datatables_always_serialize = ('id', 'href',)
        model = Submission
        fields = '__all__'

    def get_href(self, obj: Submission) -> str:
        return obj.get_absolute_url()

    def get_created_by(self, obj: Submission) -> str:
        return obj.created_by.human_readable

    def get_name(self, obj:Submission) -> str:
        t = ''
        if obj.is_part_submission:
            t = '<span class="badge text-bg-secondary ms-2">Part</span>'
        return obj.name + t

class TargetMetricValueSerializer(DynamicFieldsModelSerializer):
    key = serializers.SerializerMethodField()

    class Meta:
        model = TargetMetricValue
        fields = ('value', 'key',)

    def get_key(self, o):
        return o.target_metric.key


class EvaluationCodeSerializer(serializers.ModelSerializer):
    schema = serializers.SlugRelatedField(slug_field='identifier', queryset=GroundTruthSchema.objects.all())
    challenge = serializers.SlugRelatedField(slug_field='identifier', queryset=Challenge.objects.all())


    class Meta:
        model = EvaluationCode
        fields = ('name', 'identifier', 'pyscript', 'entrypoint', 'schema', 'challenge')

    def to_internal_value(self, data):
        data['entrypoint'] = data['entrypoint'].strip()
        return super().to_internal_value(data)
