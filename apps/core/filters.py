from django_filters import filters
from rest_framework_datatables.django_filters.filters import GlobalFilter
from rest_framework_datatables.django_filters.filterset import DatatablesFilterSet

from apps.project.project_case.models import Case
from apps.storage.models import File


class GlobalCharFilter(GlobalFilter, filters.CharFilter):
    pass

class FileFilter(DatatablesFilterSet):
    codes = GlobalCharFilter(field_name='codes__code', lookup_expr='icontains')
    name = GlobalCharFilter(lookup_expr='icontains')
    case = GlobalCharFilter(field_name='case__name', lookup_expr='icontains')
    studies = GlobalCharFilter(field_name='study_arms__study__name', lookup_expr='icontains')

    class Meta:
        model = File
        fields = ['name', 'case', 'codes', 'studies']

class CaseFilter(DatatablesFilterSet):
    # codes = GlobalCharFilter(field_name='codes__code', lookup_expr='icontains')
    name = GlobalCharFilter(lookup_expr='icontains')
    # case = GlobalCharFilter(field_name='case__name', lookup_expr='icontains')

    class Meta:
        model = Case
        fields = ['name']
