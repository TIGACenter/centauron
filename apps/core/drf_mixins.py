from django.contrib.auth.mixins import LoginRequiredMixin
from rest_framework import mixins
from rest_framework.viewsets import GenericViewSet


class DataTableViewSetBase(LoginRequiredMixin, mixins.ListModelMixin, mixins.CreateModelMixin, GenericViewSet):

    def create(self, request, **kwargs):
        return self.list(request, **kwargs)
