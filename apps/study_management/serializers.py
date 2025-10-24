from django.urls import reverse
from rest_framework import serializers

from apps.project.project_case.models import Case
from apps.storage.models import File
from apps.study_management.models import Study
from apps.study_management.tile_management.models import TileSet
from apps.viewer.templatetags.viewer_tags import viewer_url


class StudyDataTableSerializer(serializers.ModelSerializer):
    href = serializers.SerializerMethodField()

    class Meta:
        datatables_always_serialize = ('id', 'href',)
        model = Study
        fields = '__all__'

    def get_href(self, obj: Study) -> str:
        return obj.get_absolute_url()


class StudyArmCasesDataTableSerializer(serializers.ModelSerializer):
    codes = serializers.SerializerMethodField()

    class Meta:
        datatables_always_serialize = ('id', 'href', 'files')
        model = Case
        fields = '__all__'

    def get_href(self, obj: Case) -> str:
        return '#'

    def get_codes(self, obj: Case) -> str:
        return ', '.join(obj.code_list_string_rep())


class StudyArmCaseFilesDataTableSerializer(serializers.ModelSerializer):
    codes = serializers.SerializerMethodField()
    origin = serializers.SlugRelatedField(read_only=True, slug_field='human_readable')

    class Meta:
        datatables_always_serialize = ('id', 'href',)

        model = File
        fields = '__all__'

    def get_href(self, obj: File) -> str:
        return '#'

    def get_codes(self, obj: File) -> str:
        return ', '.join(obj.code_list_string_rep())


class StudyArmCaseDataTableSerializer(serializers.ModelSerializer):
    href = serializers.SerializerMethodField()
    origin = serializers.SlugRelatedField(read_only=True, slug_field='human_readable')
    codes = serializers.SerializerMethodField()

    class Meta:
        datatables_always_serialize = ('id', 'href',)
        model = Case
        fields = ('id', 'href', 'name', 'codes', 'origin', 'identifier',)

    def get_href(self, obj: Case) -> str:
        request = self.context['request']
        return reverse('study_management:add-file-to-case',
                       kwargs=dict(pk=request.query_params.get('study'), arm_pk=request.query_params.get('arm'),
                                   case_pk=obj.pk))

    def get_codes(self, obj: Case) -> str:
        return ', '.join(obj.code_list_string_rep())


class StudyArmFileDataTableSerializer(serializers.ModelSerializer):
    codes = serializers.SerializerMethodField()
    origin = serializers.SlugRelatedField(read_only=True, slug_field='human_readable')
    case = serializers.SlugRelatedField(read_only=True, slug_field='name')
    href = serializers.SerializerMethodField()
    case_id = serializers.SerializerMethodField()

    class Meta:
        datatables_always_serialize = ('id', 'href', 'case_id',)
        model = File
        fields = ('id', 'href', 'name', 'codes', 'case', 'case_id', 'imported', 'origin', 'identifier',)

    def get_href(self, obj: File) -> str:
        return viewer_url(obj)

    def get_codes(self, obj: File) -> str:
        return ', '.join(obj.code_list_code_rep())

    def get_case_id(self, obj: File):
        return obj.case_id


class StudyArmTileSetListSerializer(serializers.ModelSerializer):
    href = serializers.SerializerMethodField()
    name = serializers.CharField()
    # case = serializers.SlugRelatedField(read_only=True, slug_field='name')
    # origin = serializers.SlugRelatedField(read_only=True, slug_field='human_readable')
    tiling_params = serializers.CharField()

    class Meta:
        datatables_always_serialize = ('id', 'href',)
        model = TileSet
        fields = ('id', 'href', 'name', 'tiling_params', 'date_created', 'files_count', 'files_total_size')

    def get_href(self, obj: TileSet) -> str:
        return reverse('study_management:tile_management:detail',
                       kwargs=dict(pk=obj.study_arm.study_id, arm_pk=obj.study_arm.pk, tileset_pk=obj.pk))
