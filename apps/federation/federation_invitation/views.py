import json
import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.views import View
from django.views.generic import TemplateView, FormView

from apps.federation.federation_invitation.forms import CreateInvitationForm
from apps.federation.federation_invitation.models import FederationInvitation
from apps.federation.messages import ProjectInviteObject
from apps.federation.outbox.models import OutboxMessage
from apps.project.models import Project, ProjectMembership
from apps.user.user_profile.models import Profile


class InvitationListView(LoginRequiredMixin, TemplateView):
    template_name = 'federation/federation_invitation/list.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        ctx['received'] = FederationInvitation.objects.filter(from_identifier=user.profile.identifier)
        ctx['sent'] = FederationInvitation.objects.filter(to=self.request.user.profile)
        return ctx


class AcceptOrDeclineInvitationView(LoginRequiredMixin, View):

    def post(self, request, pk, **kwargs):
        invite = get_object_or_404(FederationInvitation, pk=pk, to=request.user.profile)
        if 'accept' in request.POST:
            invite.accept()
            messages.success(request, 'Invitation accepted.')
        else:
            invite.decline()
            messages.success(request, 'Invitation declined.')

        return redirect('project:invites')


class CreateInviteView(LoginRequiredMixin, SuccessMessageMixin, FormView):
    form_class = CreateInvitationForm
    success_message = 'Invitation sent.'
    template_name = 'federation/federation_invitation/create.html'

    def get_success_url(self) -> str:
        return reverse('project:collaborator-list', kwargs=dict(pk=self.project_id))

    def form_valid(self, form):
        # with the user search results the node data, user data and some project data are shipped.
        # import node and user here if not on the same node
        self.project_id = form.cleaned_data['project']
        R = super().form_valid(form)
        instance = form.save(commit=False)
        current_user: Profile = self.request.user.profile
        instance.to = current_user

        user = instance.from_user

        # add to project
        project_id = form.cleaned_data.get('project')
        project = Project.objects.get(pk=project_id)
        # create import-project-message
        message_object = ProjectInviteObject(sender=current_user.identifier, recipient=user.identifier,
                                             content=[project.to_message_object(),
                                                      *[dv.to_message_object() for dv in project.views.all()]])
        qs_membership = ProjectMembership.objects.filter(project_id=project_id, user=user)
        # TODO refactor all this to be in model FederationInvitation
        if not qs_membership.exists():
            project_membership = ProjectMembership.objects.create(user=user, project=project, invite=instance)
            project_data = json.loads(message_object.model_dump_json())
            instance.project_data = project_data
            instance.save()
            # add to invitee to the inviter's allow list to be able to receive the response
            current_user.communication_allowed_with_users.add(user)
            msg = OutboxMessage.create(sender=current_user,
                                     recipient=user,
                                     message_object=message_object)
            if user.node != current_user.node:
                msg.send()
            else:
                project_data = msg.message
                msg.delete()
                fi = FederationInvitation.objects.create(
                    to=user,
                    from_user=current_user,
                    project_data=project_data,
                    project=project
                )
                fi.project_membership.add(project_membership)
        else:
            messages.error(self.request, 'User is already a member of this project.')
        return R

    def form_invalid(self, form):
        messages.error(self.request, ','.join(form.errors))
        return self.form_valid(form)


class SearchForCollaboratorView(LoginRequiredMixin, TemplateView):
    template_name = 'federation/federation_invitation/search.html'


class QueryView(LoginRequiredMixin, TemplateView):

    def post(self, request, **kwargs):
        query = request.POST.get('query')
        try:
            response = Profile.objects.filter(human_readable__icontains=query).exclude(human_readable=settings.NODE_NAME)
        except Exception as e:
            logging.exception(e)
            return render(request, 'federation/federation_invitation/error.html', {'message': str(e)})

        ctx = {'data': response,
               'project': Project.objects.for_user(request.user.profile).filter(pk=request.GET.get('project')).first()}
        return render(request, 'federation/federation_invitation/table.html', ctx)
