from rest_framework import serializers

from apps.core.serializers import IdentifierField, DynamicFieldsModelSerializer
from apps.storage.models import File


class DataTableFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = File
        fields = '__all__'


class FileSerializer(DynamicFieldsModelSerializer):
    origin = IdentifierField(read_only=True)
    identifier = serializers.StringRelatedField()
    case = IdentifierField(read_only=True)
    datasets = serializers.SerializerMethodField()

    def __init__(self, *args, **kwargs):
        if 'contained_datasets' in kwargs:
            self.contained_datasets = kwargs.pop('contained_datasets')
        else:
            self.contained_datasets = None
        super().__init__(*args, **kwargs)

    class Meta:
        model = File
        fields = ('identifier', 'name', 'content_type', 'origin', 'datasets', 'case', 'path',
                  'original_filename', 'original_path', 'size')

    def get_datasets(self, obj: File):
        qs = obj.datasets.all()
        if self.contained_datasets is not None:
            qs = qs.filter(id__in=self.contained_datasets)
        reps = IdentifierField(many=True, read_only=True).to_representation(qs)
        return reps
