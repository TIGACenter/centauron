from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from rest_framework import viewsets

from apps.project.project_case import serializers
from apps.project.project_case.models import Case
from apps.project.models import DataView


class CaseTableView(LoginRequiredMixin, viewsets.ModelViewSet):
    serializer_class = serializers.DataTableCaseSerializer

    def get_queryset(self):
        project_id = self.request.GET.get('project', None)
        view_id = self.request.GET.get('view', None)
        filter_kwargs = {}
        if view_id is not None:
            view = DataView.objects.get(pk=view_id, project_id=project_id)
            filter_kwargs = view.query
        objects_filter = Case.objects.filter(projects=project_id,
                                             projects__created_by=self.request.user.profile,
                                             **filter_kwargs)
        return objects_filter

    def destroy(self, request, *args, **kwargs):
        return HttpResponse(status=400)

    def retrieve(self, request, *args, **kwargs):
        return HttpResponse(status=400)

    def create(self, request, **kwargs):
        return self.list(request, **kwargs)

