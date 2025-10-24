import logging

from django.conf import settings
from django.db import models

from apps.core.models import Base
from apps.federation.messages import ProjectInviteResponseObject, ProjectInviteResponseContent, Message
from apps.federation.outbox.models import OutboxMessage
from apps.node.models import Node


class FederationInvitation(Base):
    class Status(models.TextChoices):
        ACCEPTED = 'accepted'
        DECLINED = 'declined'
        OPEN = 'open'

    status = models.CharField(choices=Status.choices, default=Status.OPEN, max_length=8)
    from_user = models.ForeignKey('user_profile.Profile', on_delete=models.CASCADE,
                                  related_name='federation_invitations_sent')
    # from_name = models.CharField(max_length=100)
    # from_identifier = models.CharField(max_length=100)
    # from_organization = models.CharField(max_length=100, blank=True, default=None, null=True)
    to = models.ForeignKey('user_profile.Profile', on_delete=models.CASCADE, related_name='federation_invitations')
    # remote_invite_id = models.CharField(max_length=100, blank=True, null=True, default=None)
    # node_data = models.JSONField()
    project_data = models.JSONField()
    project = models.ForeignKey('project.Project', on_delete=models.CASCADE, related_name='invitations', null=True,
                                default=None)

    def accept(self):
        self.respond(True)

    def decline(self):
        self.respond(False)

    def respond(self, accept: bool):
        on_same_node = self.from_user.node is not None and self.from_user.node.identifier == settings.IDENTIFIER
        # add user to allow list to enable future communications
        self.to.communication_allowed_with_users.add(self.from_user)

        project_identifier = ''
        for c in self.project_data['object']['content']:
            if c['type'] == 'project':
                project_identifier = c['identifier']
                break

        if accept:
            self.status = FederationInvitation.Status.ACCEPTED
            if not on_same_node:
                msg = Message(**self.project_data)
                from apps.project.models import Project
                logging.info(msg)
                Project.import_project(message=msg, invitation=self)
        else:
            self.status = FederationInvitation.Status.DECLINED

        self.save(update_fields=['status'])

        if not on_same_node:
            object = ProjectInviteResponseObject(
                content=ProjectInviteResponseContent(
                    project=project_identifier,
                    accept=accept
                ))
            OutboxMessage.create(sender=self.to, recipient=self.from_user, message_object=object).send()

        # TODO send log message "User joined project XYZ"
