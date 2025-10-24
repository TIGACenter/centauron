from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from rest_framework import viewsets, mixins

from apps.challenge.challenge_submission import serializers
from apps.challenge.challenge_submission.models import Submission


class SubmissionDataTableView(LoginRequiredMixin, viewsets.GenericViewSet, mixins.CreateModelMixin, mixins.ListModelMixin):
    serializer_class = serializers.SubmissionDataTableSerializer

    def get_queryset(self):
        return Submission.objects.filter(origin__isnull=False, challenge_id=self.kwargs.get('pk')).order_by('-date_created').prefetch_related('origin')

    def create(self, request, **kwargs):
        return self.list(request, **kwargs)
