from rest_framework import serializers
from rest_framework.fields import ListField

from apps.core.serializers import IdentifierField, DynamicFieldsModelSerializer
from apps.project.project_case.models import Case


class CaseSerializer(DynamicFieldsModelSerializer):
    identifier = serializers.StringRelatedField()
    origin = IdentifierField(read_only=True)
    # datasets = IdentifierField(many=True, read_only=True)
    datasets = serializers.SerializerMethodField()

    def __init__(self, *args, **kwargs):
        if 'contained_datasets' in kwargs:
            self.contained_datasets = kwargs.pop('contained_datasets')
        else:
            self.contained_datasets = None
        super().__init__(*args, **kwargs)


    class Meta:
        model = Case
        fields = ('identifier', 'datasets', 'name', 'origin')

    def get_datasets(self, obj:Case):
        qs = obj.datasets.all()
        if self.contained_datasets is not None:
            qs = qs.filter(id__in=self.contained_datasets)
        reps = ListField(child=IdentifierField(read_only=True)).to_representation(qs)
        # reps = IdentifierField(many=True, read_only=True).to_representation(qs) # many=True
        return reps

class DataTableCaseSerializer(CaseSerializer):
    href = serializers.SerializerMethodField()
    files_count = serializers.SerializerMethodField()
    files = serializers.SerializerMethodField()
    origin = serializers.SerializerMethodField()
    terms = serializers.SerializerMethodField()

    class Meta:
        datatables_always_serialize = ('id', 'href', 'files')
        model = Case
        fields = '__all__'

    def get_href(self, obj: Case) -> str:
        return '#'  # obj.get_absolute_url()

    def get_files_count(self, obj: Case):
        return str(obj.files.count())

    def get_files(self, obj: Case):
        return [dict(name=f.original_filename, annotations=[(a.system, a.value) for a in f.annotations.all()]) for
                f in
                obj.files.all()]

    def get_origin(self, obj:Case):
        return obj.origin.human_readable

    def get_terms(self, obj:Case):
        return obj.code_list_string_rep()
