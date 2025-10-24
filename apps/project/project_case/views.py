from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render
from django.views.generic import FormView, CreateView

from apps.project.project_case.forms import CaseForm


class CreateCaseFormView(LoginRequiredMixin, CreateView):
    template_name = 'project/project_case/create.html'
    form_class = CaseForm
