from rest_framework_datatables.django_filters.backends import DatatablesFilterBackend

from apps.core.drf_mixins import DataTableViewSetBase
from apps.core.filters import FileFilter, CaseFilter
from apps.project.project_case.models import Case
from apps.storage.models import File
from apps.study_management import serializers
from apps.study_management.models import Study, StudyArm
from apps.study_management.tile_management.models import TileSet


class StudyDataTableView(DataTableViewSetBase):
    serializer_class = serializers.StudyDataTableSerializer

    def get_queryset(self):
        return Study.objects.for_user(self.request.user.profile)


class StudyArmCaseFileTableView(DataTableViewSetBase):
    serializer_class = serializers.StudyArmCaseFilesDataTableSerializer

    def get_queryset(self):
        return File.objects.filter(case_id=self.request.GET.get('case')) \
            .prefetch_related('annotations', 'codes', 'origin')


class StudyArmCaseTableView(DataTableViewSetBase):
    serializer_class = serializers.StudyArmCaseDataTableSerializer
    filter_backends = (DatatablesFilterBackend,)
    filterset_class = CaseFilter

    def get_queryset(self):
        sa = StudyArm.objects.get(pk=self.request.GET.get('arm'), study__created_by=self.request.user.profile)
        return Case.objects.filter(id__in=sa.files.values_list('case', flat=True).distinct(),
                                   created_by=self.request.user.profile).prefetch_related('codes', 'origin')


class StudyArmFileTableView(DataTableViewSetBase):
    serializer_class = serializers.StudyArmFileDataTableSerializer
    filter_backends = (DatatablesFilterBackend,)
    filterset_class = FileFilter

    def get_queryset(self):
        sa: StudyArm = StudyArm.objects.get(pk=self.request.GET.get('arm'), study__created_by=self.request.user.profile)
        return File.objects.filter(study_arms=sa,
                                   created_by=self.request.user.profile).prefetch_related('annotations', 'codes',
                                                                                          'origin', 'case')


class StudyArmTileSetListSet(DataTableViewSetBase):
    serializer_class = serializers.StudyArmTileSetListSerializer

    def get_queryset(self):
        # arm = get_object_or_404(StudyArm, pk=self.request.GET.get('arm', None),
        #                         study=self.request.GET.get('study'),
        #                         study__created_by=self.request.user.profile)
        # b = arm.tilesets.all()
        t = TileSet.objects.filter(study_arm=self.request.GET.get('arm', None)).all()
        return t
        # return b
