from django.db import models

from apps.core.models import Base
from apps.node.models import Node


class Event(Base):
    class Verb(models.TextChoices):
        PROJECT_CREATE = 'project_create'
        PROJECT_MEMBER_INVITE = 'project_invite'
        PROJECT_MEMBER_INVITE_ACCEPTED = 'project_invite_accept'
        PROJECT_MEMBER_INVITE_DECLINED = 'project_invite_decline'
        PROJECT_MEMBER_REMOVED = 'project_member_removed'
        SHARE_RECEIVE = 'share_receive'

    verb = models.CharField(max_length=200, choices=Verb.choices)
    context_project = models.ForeignKey('project.Project', null=True, on_delete=models.CASCADE,
                                        related_name='event_contexts')
    object_project = models.ForeignKey('project.Project', null=True, on_delete=models.CASCADE,
                                       related_name='event_objects')
    object_node = models.ForeignKey('node.Node', null=True, on_delete=models.CASCADE,
                                       related_name='event_objects')

    subject = models.ForeignKey('user_profile.Profile', on_delete=models.CASCADE,
                                null=True)  # TODO if subject is deleted, subject.human_readable should be written into an extra field to keep the event history consistent.

    @staticmethod
    def create(subject: 'Profile', verb: Verb, context, object=None):  # context and object are of type project
        from apps.project.models import Project
        k = None
        if isinstance(object, Project):
            k = 'object_project'
        if isinstance(object, Node):
            k = 'object_node'
        kw = {}
        if k is not None:
            kw[k] = object
        return Event.objects.create(subject=subject,
                                    verb=verb,
                                    context_project=context, **kw)
