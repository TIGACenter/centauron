import logging

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.urls import reverse_lazy
from django.views.generic import FormView

from apps.user.user_profile.forms import ProfileForm


class UpdateProfileView(LoginRequiredMixin, SuccessMessageMixin, FormView):
    template_name = 'users/profile_form.html'
    form_class = ProfileForm
    success_message = 'Profile successfully updated.'
    success_url = reverse_lazy('user:profile:form')

    def get_form_kwargs(self, **kwargs):
        ctx = super().get_form_kwargs(**kwargs)
        ctx['instance'] = self.request.user.profile
        return ctx

    def form_valid(self, form):
        profile = form.save()
        if 'save_and_publish' in form.data:
            try:
                profile.publish_to_registry()
                messages.success(self.request, 'Published to registry.')
            except Exception as e:
                logging.exception(e)
                messages.error(self.request, f'Error publishing to registry: {e}.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update({'profile': self.request.user.profile})
        return ctx
