import logging

from annoying.fields import AutoOneToOneField
from django.db import models, transaction
from django.urls import reverse

from apps.blockchain.messages import CreateMessage, Identifiable, Object
from apps.blockchain.models import Log
from apps.core.models import Base, CreatedByMixin, IdentifieableMixin, OriginMixin
from apps.event.models import Event
from apps.federation.federation_invitation.models import FederationInvitation
from apps.federation.messages import ProjectMessageContent, ProjectObject, Message, ProjectInviteAcceptMessage, \
    ProjectInvitationObject, DataViewMessageContent, ProjectInviteObject
from apps.federation.outbox.models import OutboxMessage
from apps.node.models import Node
from apps.project.manager import ProjectManager
from apps.user.user_profile.models import Profile


class Project(CreatedByMixin, OriginMixin, IdentifieableMixin, Base):
    objects = ProjectManager()
    name = models.CharField(max_length=500)
    description = models.TextField(blank=True, null=True)
    files = models.ManyToManyField('storage.File', blank=True, related_name='projects', through='FilePermission')
    codeset = AutoOneToOneField('terminology.CodeSet', on_delete=models.SET_NULL, default=None, null=True, blank=True,
                                related_name='project')

    extra_data = models.ManyToManyField('extra_data.ExtraData', blank=True, related_name='projects', through='ProjectExtraData')

    def __str__(self):
        return self.name

    def get_project_members(self):
        return self.members.filter(invite__status=FederationInvitation.Status.ACCEPTED)

    @property
    def latest_ground_truth_schema(self):
        return self.ground_truth_schemas.order_by('-date_created').first()

    @property
    def has_codeset(self):
        return self.codeset is not None

    def user_is_owner(self, user: 'Profile'):
        return self.origin.identifier == user.identifier

    def files_for_user(self, user: 'Profile'):
        from apps.storage.models import File
        return File.objects.filter(
            pk__in=self.files.through.objects.filter(project=self, user=user).values_list('file_id', flat=True))

    def extra_data_for_user(self, user: 'Profile'):
        from apps.storage.extra_data.models import ExtraData
        return ExtraData.objects.filter(
            pk__in=self.extra_data.through.objects.filter(project=self, user=user).values_list('extra_data_id', flat=True))

    def to_message_object(self) -> ProjectMessageContent:
        return ProjectMessageContent(id=self.id_as_str,
                                     identifier=self.identifier,
                                     name=self.name,
                                     description=self.description,
                                     origin=self.origin.identifier)

    def add_member(self, user: 'Profile', invitation=None):
        with transaction.atomic():
            ProjectMembership.objects.create(user=user, project=self, invite=invitation)

            # mo = ProjectObject(content=[self.to_message_object()])
            #
            # om = OutboxMessage.create(recipient=user,
            #                           sender=self.created_by,
            #                           message_object=mo)
            # om.extra_data = dict(
            #     resource='task',
            #     method='post',
            #     process=constants.INVITE_REQUEST_PROCESS,
            #     message_name='inviteNode',
            #     profile=constants.INVITE_REQUEST_TASK_INVITE_PROFILE,
            #     input=[]
            # )
            # om.save(update_fields=['extra_data'])
            # om.send()
            # TODO
            # Event.create(get_node_origin(), Event.Verb.PROJECT_MEMBER_INVITE, self, object=node)

    def remove_member(self, current_user, member_pk):
        n = self.members.filter(pk=member_pk).first()
        Event.create(current_user, Event.Verb.PROJECT_MEMBER_REMOVED, self, object=n.user)
        n.delete()
        return n
        # TODO start DSF process to remove member

    @staticmethod
    def import_project_invitation(**kwargs):
        # TODO test this
        message: Message = kwargs['message']
        object: ProjectInviteObject = message.object
        # TODO check if sender and recipient exist on this node
        from_ = Profile.objects.get_by_identifier(object.sender)
        to = Profile.objects.get_by_identifier(object.recipient)

        FederationInvitation.objects.create(
            from_user=from_,
            to=to,
            project_data=kwargs.get('inbox_message').message,
        )

    @staticmethod
    def process_invitation_response(**kwargs):
        from apps.federation.inbox.models import InboxMessage
        message: Message = kwargs['message']
        inbox_message: InboxMessage = kwargs.get('inbox_message')

        o: ProjectInvitationObject = message.object
        logging.info(o.content)
        logging.info(message.object)
        c: ProjectInviteAcceptMessage = ProjectInviteAcceptMessage(**o.content)

        project = Project.objects.filter_by_identifier(c.project)
        if not project.exists():
            logging.error('No project with identifier %s exists.', c.project)
            return
        project = project.first()
        new_status = FederationInvitation.Status.ACCEPTED if c.accept else FederationInvitation.Status.DECLINED
        membership:ProjectMembership = project.members.filter(user=inbox_message.sender).first()
        membership.invite.status = new_status
        membership.invite.save()

        # event_verb = Event.Verb.PROJECT_MEMBER_INVITE_DECLINED
        if new_status == FederationInvitation.Status.ACCEPTED:
            # TODO add ground truth here
            content = [project.to_message_object(), *[dv.to_message_object() for dv in project.views.all()]]
            gt = project.latest_ground_truth_schema
            if gt is not None:
                content.append(gt.to_message_object())

            om = OutboxMessage.create(recipient=inbox_message.sender,
                                      sender=project.created_by,
                                      message_object=ProjectObject(content=content))
            om.send()
            event_verb = Event.Verb.PROJECT_MEMBER_INVITE_ACCEPTED
        # TODO
        # Event.create(inbox_message.sender, event_verb, project)

    @staticmethod
    def import_project(**kwargs):
        from apps.federation.inbox.models import InboxMessage
        message: Message = kwargs['message']
        invitation = kwargs.get('invitation')
        # inbox_message: InboxMessage = kwargs.get('inbox_message')

        o: ProjectObject = message.object
        project = None
        with transaction.atomic():
            # TODO make sure that project is imported first
            for i in o.content:
                if i['type'] == 'project':
                    c: ProjectMessageContent = ProjectMessageContent(**i)
                    # TODO check if project with this identifier already exists. if so, do not create but maybe just update?
                    from apps.user.user_profile.models import Profile
                    origin = Profile.objects.get_by_identifier(o.sender)
                    project = Project.objects.create(
                        name=c.name,
                        identifier=c.identifier,
                        description=c.description,
                        origin=origin
                    )

                    project.add_member(origin, invitation)
                    project.add_member(Profile.objects.get_by_identifier(o.recipient), invitation)
                if i['type'] == 'data-view':
                    c: DataViewMessageContent = DataViewMessageContent(**i)
                    DataView.import_(c, project)
            # TODO some logging that project was imported

    def to_identifiable(self):
        return Identifiable(identifier=self.identifier, display=self.name, model="project")

    def broadcast_create_message(self):
        Log.send_broadcast(
            CreateMessage(object=Object(model="project", value=self.to_identifiable()),
                          actor=self.created_by.to_actor()),
        send_async=True)


class ProjectMembership(Base):
    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['project', 'user'], name='unique_user_in_project')
        ]

    # must be foreign key and no OneToOneField as a federation invitation on the same node reference the same membership.
    invite = models.ForeignKey('federation_invitation.FederationInvitation',
                               on_delete=models.SET_NULL,
                               null=True,
                               related_name='project_membership')
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='members')
    user = models.ForeignKey('user_profile.Profile', on_delete=models.CASCADE, related_name='projects')

    def __str__(self):
        return f'{self.user} {self.project}'


class DataView(CreatedByMixin, Base):
    class Model(models.TextChoices):
        CASE = 'case'
        FILE = 'file'

    name = models.CharField(max_length=100)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='views')
    query = models.JSONField(default=dict, blank=True)
    # datatable_config = models.JSONField(default=dict, blank=True)
    datatable_config = models.TextField(default='', blank=True)
    model = models.CharField(choices=Model.choices, default=Model.CASE, max_length=10)
    js = models.TextField(default='', blank=True)

    def __str__(self):
        return f'{self.name} ({self.project.name})'

    def get_base_url(self):
        if self.model == DataView.Model.CASE:
            key = 'project:project_case:case-list'
        else:
            key = 'project:datatable-file-list'
        return reverse(key)

    def get_absolute_url(self):
        return reverse('project:detail', kwargs=dict(pk=self.project_id)) + f'?v={self.id}'

    def to_message_object(self) -> DataViewMessageContent:
        return DataViewMessageContent(
            name=self.name,
            query=self.query,
            datatable_config=self.datatable_config,
            model=self.model
        )

    @staticmethod
    def import_(content: DataViewMessageContent, project: Project, **kwargs):
        DataView.objects.create(
            project=project,
            name=content.name,
            query=content.query,
            datatable_config=content.datatable_config,
            model=content.model
        )


class FilePermission(Base):
    """
    Represents a tuple (project, file, user) and therefore which file is for which user in which project imported.
    """
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    user = models.ForeignKey('user_profile.Profile', on_delete=models.CASCADE)
    file = models.ForeignKey('storage.File', on_delete=models.CASCADE)
    imported = models.BooleanField(default=False)


class ProjectExtraData(Base):
    """
    Represents a tuple (project, extra_data, user) and therefore which extra_data is for which user in which project imported.
    """
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    user = models.ForeignKey('user_profile.Profile', on_delete=models.CASCADE)
    extra_data = models.ForeignKey('extra_data.ExtraData', on_delete=models.CASCADE)
    imported = models.BooleanField(default=False)
