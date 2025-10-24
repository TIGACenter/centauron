from rest_framework import serializers
from rest_framework_datatables.django_filters.backends import DatatablesFilterBackend

from apps.core.drf_mixins import DataTableViewSetBase
from apps.core.filters import FileFilter
from apps.project.models import DataView, FilePermission, Project, ProjectExtraData
from apps.share.models import Share
from apps.storage.models import File
from apps.storage.serializers import DataTableFileSerializer
from apps.study_management.models import Study
from apps.user.user_profile.models import Profile
from apps.viewer.templatetags.viewer_tags import viewer_url


class OriginFieldSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = ('human_readable',)


class DataTableDataTableFileSerializer(DataTableFileSerializer):
    href = serializers.SerializerMethodField()
    origin = OriginFieldSerializer(read_only=True)
    case = serializers.SlugRelatedField(read_only=True, slug_field='name')
    terms = serializers.SerializerMethodField()
    imported = serializers.SerializerMethodField()
    studies = serializers.SerializerMethodField()
    annotation_count = serializers.SerializerMethodField()

    class Meta:
        datatables_always_serialize = ('id', 'href', 'imported', 'annotation_count')
        model = File
        fields = DataTableFileSerializer.Meta.fields  # + ('terms', )

    def get_imported(self, obj):
        fp = self.context['qs'].filter(file_id=obj.pk).first()
        return fp.imported

    def get_annotation_count(self, obj):
        # TODO this is now for all users and not for a file in a single study.
        # TODO this is not for annotations per se but as of now 24.02.2025 only annotations from exact are stored in ExtraData so that works.
        return self.context['qs_extradata'].filter(extra_data__file=obj).count()

    def get_href(self, obj: File) -> str:
        # if the file is imported for the requesting user, return the viewer url here
        fp = self.context['qs'].filter(file_id=obj.pk).first()
        if fp.imported:
            return viewer_url(obj)
        return '#'

    def get_terms(self, obj: File):
        return ', '.join(obj.code_list_string_rep())

    def get_studies(self, obj: File):
        studies = Study.objects.filter(id__in=(obj.study_arms.values_list('study_id', flat=True).distinct()))
        return [{'id': s.id_as_str, 'name': s.name, 'href': s.get_absolute_url()} for s in studies]
        # return ', '.join([s.name for s in studies])


class SharedWithMeSerializer(serializers.ModelSerializer):
    href = serializers.SerializerMethodField()
    from_ = serializers.SerializerMethodField()

    class Meta:
        datatables_always_serialize = ('id', 'href')
        model = Share
        fields = '__all__'

    def get_href(self, obj: Share) -> str:
        return '#'  # obj.get_absolute_url()

    def get_from_(self, obj: Share) -> str:
        return str(obj.data.origin)


class FileTableView(DataTableViewSetBase):
    serializer_class = DataTableDataTableFileSerializer
    filter_backends = (DatatablesFilterBackend,)
    filterset_class = FileFilter

    # filter_backends = [DjangoFilterBackend]
    # filterset_fields = ['name']

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['qs'] = FilePermission.objects.filter(project_id=self.request.GET.get('project'),
                                                  user=self.request.user.profile)
        ctx['qs_extradata'] = ProjectExtraData.objects.filter(
            project_id=self.request.GET.get('project'),
            user=self.request.user.profile,
            imported=True)
        return ctx

    def get_queryset(self):
        project_id = self.request.GET.get('project')
        view_id = self.request.GET.get('view')

        filter_kwargs = {}
        if view_id is not None:
            view = DataView.objects.get(pk=view_id, project_id=project_id)
            filter_kwargs = view.query
        objects_filter = Project.objects.get(pk=project_id).files_for_user(self.request.user.profile).filter(**filter_kwargs).prefetch_related('origin')
        # objects_filter = File.objects.filter(filepermission__project_id=project_id,
        #                                      filepermission__user=self.request.user.profile,
        #                                      **filter_kwargs).prefetch_related('origin')
        # p = Project.objects.get(pk=project_id, members__in=self.request.current_user.profile)
        # p.files.through.objects.filter()
        return objects_filter


class SharedWithMeTableView(DataTableViewSetBase):
    serializer_class = SharedWithMeSerializer

    def get_queryset(self):
        return Share.objects.filter(created_by=self.request.user.profile)
