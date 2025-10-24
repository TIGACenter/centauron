from rest_framework import serializers
from rest_framework.relations import StringRelatedField

from apps.challenge.challenge_dataset.models import Dataset
from apps.core.serializers import IdentifierField, DynamicFieldsModelSerializer
from apps.storage.models import File


class DatasetSerializer(DynamicFieldsModelSerializer):
    identifier = StringRelatedField()
    challenge = IdentifierField(read_only=True)
    origin = IdentifierField(read_only=True)

    class Meta:
        model = Dataset
        fields = ('identifier', 'origin', 'challenge', 'name', 'type', 'description')


class DatasetDataTableSerializer(serializers.ModelSerializer):
    href = serializers.SerializerMethodField()

    class Meta:
        datatables_always_serialize = ('id', 'href',)
        model = Dataset
        fields = '__all__'

    def get_href(self, obj: Dataset) -> str:
        return obj.get_absolute_url()


# example:
class FileSerializer(serializers.ModelSerializer):
    href = serializers.SerializerMethodField()
    case = serializers.SerializerMethodField()

    class Meta:
        datatables_always_serialize = ('id', 'href',)
        model = File
        fields = '__all__'

    def get_href(self, obj: File) -> str:
        return '#'  # obj.get_absolute_url()

    def get_case(self, obj: File) -> str:
        return obj.case.name
