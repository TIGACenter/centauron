from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, get_object_or_404
from django.views.generic import TemplateView

from apps.computing.computing_executions.models import ComputingJobExecution


class LogView(LoginRequiredMixin, TemplateView):
    template_name = 'computing/computing_executions/log.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        e = get_object_or_404(ComputingJobExecution,
                              pk=self.kwargs.get('pk'),
                              definition__created_by=self.request.user.profile)
        ctx['execution'] = e
        return ctx
