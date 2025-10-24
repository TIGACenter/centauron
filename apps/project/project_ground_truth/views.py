from typing import Any

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.shortcuts import redirect
from django.urls import reverse
from django.views import View
from django.views.generic import FormView, TemplateView

from apps.project.project_ground_truth.forms import GroundTruthSchemaForm
from apps.project.views import ProjectContextMixin


class GroundTruthSchemaView(LoginRequiredMixin, SuccessMessageMixin, ProjectContextMixin, FormView):
    template_name = 'project/project_ground_truth/ground_truth.html'
    form_class = GroundTruthSchemaForm
    success_message = 'Schema saved.'

    def get_success_url(self) -> str:
        return reverse('project:ground_truth:ground-truth-schema', kwargs=dict(pk=self.get_project_id()))

    def get_context_data(self, **kwargs):
        # TODO only project owner can see this page
        ctx = super().get_context_data(**kwargs)
        ctx['object'] = self.get_project().latest_ground_truth_schema
        return ctx

    def get_form_kwargs(self) -> dict[str, Any]:
        ctx = super().get_form_kwargs()
        ctx['instance'] = self.get_project().latest_ground_truth_schema
        return ctx

    def form_valid(self, form):
        form.save(**dict(created_by=self.request.user.profile, project=self.get_project()))
        return super().form_valid(form)


class SendToCollaboratorsView(LoginRequiredMixin, ProjectContextMixin, View):

    def post(self, request, pk, **kwargs):
        self.get_project().latest_ground_truth_schema.distribute()
        messages.success(request, 'Ground Truth Schema will be sent to contributors.')
        return redirect('project:ground_truth:ground-truth-schema', pk=self.get_project_id())


class GroundTruthSchemaDetailView(LoginRequiredMixin,ProjectContextMixin, TemplateView):
    template_name = 'project/project_ground_truth/detail.html'

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        project = ctx['project']
        ctx['object'] = project.ground_truth_schemas.get(pk=self.kwargs['gt_pk'])
        return ctx
