from datetime import timedelta
from typing import Any, Dict
from uuid import UUID

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView, DetailView, FormView, UpdateView

from apps.challenge import tasks, forms
from apps.challenge.challenge_dataset.models import EvaluationCode
from apps.challenge.forms import CreateChallengeForm, EvaluationCodeForm
from apps.challenge.models import Challenge
from apps.core import identifier
from apps.federation.federation_invitation.models import FederationInvitation
from apps.utils import get_node_origin


class ChallengeContextMixin:

    def get_challenge_id(self) -> UUID | None:
        return self.kwargs.get('pk')

    def get_challenge(self) -> Challenge:
        return Challenge.objects.for_user(self.request.user.profile).get(pk=self.get_challenge_id())

    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        ctx['challenge'] = self.get_challenge()
        return ctx

class ListView(LoginRequiredMixin, TemplateView):
    template_name = 'challenge/list.html'

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        ctx.update({
            'objects': Challenge.objects.for_user(self.request.user.profile).order_by('-date_created')
        })
        return ctx


class SingleView(LoginRequiredMixin, DetailView):
    template_name = 'challenge/challenge_dataset/tab.html'

    def get_queryset(self):
        return Challenge.objects.all()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update({'tab': 'datasets'})
        return ctx


class RedirectToDatasetListView(LoginRequiredMixin, View):
    def get(self, request, **kwargs):
        return redirect('challenge:challenge_dataset:list', **kwargs)


class BaseTabView(LoginRequiredMixin, DetailView):
    template_name = 'challenge/challenge_dataset/tab.html'

    def get_tab_name(self):
        raise NotImplementedError()

    def get_queryset(self):
        return Challenge.objects.all()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update({'tab': self.get_tab_name()})
        return ctx


class PublishView(LoginRequiredMixin, ChallengeContextMixin, TemplateView):
    template_name = 'challenge/publish.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        challenge = ctx['challenge']
        ctx.update({
            'public_datasets': challenge.datasets.filter(is_public=True),
            'target_metrics': challenge.target_metrics.all(),
            'publishing_endpoints': challenge.project.members.filter(
                invite__status=FederationInvitation.Status.ACCEPTED)
            .exclude(user__node=get_node_origin())
            # TODO add hub here or is it better to add the hub as a project member??
        })
        return ctx

    def post(self, request, pk, **kwargs):
        challenge = self.get_challenge()
        messages.success(request, 'Challenge will be published in background.')
        datasets = request.POST.getlist('datasets', [])
        tasks.share_challenge.delay(str(request.user.profile.id_as_str),
                                    challenge.id_as_str,
                                    datasets,
                                    request.POST.get('publishing-endpoint'))
        return redirect(challenge)


class CreatePipelineView(LoginRequiredMixin, ChallengeContextMixin, FormView):
    template_name = 'challenge/create-pipeline.html'
    form_class = forms.CreatePipelineForm

    def form_valid(self, form):
        data = form.cleaned_data
        created_by = self.request.user.profile
        challenge = self.get_challenge()
        challenge.pipeline_yml = data['yml']
        challenge.save()

        # parse and create pipeline
        tasks.create_pipeline_from_yml(challenge.id_as_str, created_by.id_as_str)  # TODO .delay
        return redirect(challenge)

class CreateChallengeView(LoginRequiredMixin, FormView):
    form_class = CreateChallengeForm
    template_name = 'challenge/create.html'

    def get_success_url(self) -> str:
        return reverse('challenge:detail', kwargs=dict(pk=self.object.pk))

    def form_valid(self, form):
        self.object = form.save(**dict(created_by=self.request.user.profile))
        self.object.send_created_broadcast()
        return super().form_valid(form)

    def get_form_kwargs(self) -> dict[str, Any]:
        ctx = super().get_form_kwargs()
        ctx['user'] = self.request.user.profile
        return ctx

    def get_initial(self) -> dict[str, Any]:
        now = timezone.now()
        return {
            'open_from': now,
            'open_until': now + timedelta(days=365)
        }


class EvaluationCodeView(LoginRequiredMixin, SuccessMessageMixin, ChallengeContextMixin, FormView):
    form_class = EvaluationCodeForm
    template_name = 'challenge/evaluation-code.html'
    success_message = 'Evaluation Code saved.'

    def get_evaluation_code(self):
        return self.get_challenge().evaluationcode_set.first()

    def get_form_kwargs(self) -> dict[str, Any]:
        ctx = super().get_form_kwargs()
        qs = self.get_evaluation_code()
        if qs is not None:
            ctx['instance'] = qs
        ctx['project'] = self.get_challenge().project
        return ctx

    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        ctx= super().get_context_data(**kwargs)
        ctx['object'] = self.get_evaluation_code()
        return ctx

    def form_valid(self, form):
        if form.instance._state.adding:
            form.instance.challenge = self.get_challenge()
            form.instance.identifier = identifier.create_random('evaluation-code')

        form.save()
        messages.success(self.request, self.get_success_message(form.cleaned_data))
        return redirect('challenge:evaluation-code', self.get_challenge_id())

    def form_invalid(self, form):
        return super().form_invalid(form)

class UpdateChallengeFormView(LoginRequiredMixin, SuccessMessageMixin, ChallengeContextMixin, UpdateView):
    form_class = forms.UpdateChallengeForm
    template_name = 'challenge/update.html'
    success_message = 'Challenge updated.'

    def get_object(self, queryset = ...):
        return self.get_challenge()

    def get_success_url(self) -> str:
        return reverse('challenge:update', kwargs={'pk': self.get_challenge_id()})

    def get_form_kwargs(self) -> dict[str, Any]:
        kw = super().get_form_kwargs()
        kw['instance'] = self.get_challenge()
        return kw
