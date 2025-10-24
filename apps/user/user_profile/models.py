import logging
import secrets

from annoying.fields import AutoOneToOneField
from constance import config
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models
from rest_framework.authtoken.models import Token
from web3 import Web3

from apps.blockchain.messages import Actor, CreateMessage, Object, Identifiable
from apps.core import identifier
from apps.core.models import Base, IdentifieableMixin
from apps.federation.messages import UserMessage, UserMessageContent, ProfileMessage, ProfileMessageContent, \
    UpdateMessage, Message
from apps.node.models import Node
from apps.share.share_token import token_utils
from apps.user.user_group.models import Group
from apps.user.user_profile.managers import ProfileManager

User = get_user_model()


class Profile(IdentifieableMixin, Base):
    objects = ProfileManager()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['identifier'], name='unique_identifier_per_profile')
        ]

    user = AutoOneToOneField(User, on_delete=models.CASCADE, null=True, default=None, blank=True)
    group = models.ForeignKey(Group, on_delete=models.CASCADE, null=True, blank=True, default=None,
                              related_name='members')
    human_readable = models.CharField(max_length=100)

    organization = models.CharField(max_length=100, null=True, default=None, blank=True)
    orcid = models.URLField(blank=True, null=True, default=None)
    pubmed = models.URLField(blank=True, null=True, default=None)
    google_scholar = models.URLField(blank=True, null=True, default=None)

    is_published = models.BooleanField(default=False)

    node = models.ForeignKey('node.Node', on_delete=models.CASCADE, related_name='users',
                             null=True)

    # the identifier of the identity in firefly
    identity = models.CharField(max_length=100, unique=True)

    # contains all users from other nodes that are allowed to send a message to this user
    communication_allowed_with_users = models.ManyToManyField('Profile', blank=True,
                                                              help_text='The list of users allowed to send a message to this particular user.')

    private_key = models.CharField(max_length=100, blank=True, null=True)
    eth_address = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return self.human_readable

    @property
    def has_private_key(self):
        return self.private_key is not None

    def get_private_key(self):
        if self.private_key is None:
            return None

        return (settings.PRIVATE_KEY_FOLDER / self.private_key).read_text()

    def generate_private_key(self):
        extra_entropy = secrets.token_hex(32)
        w3 = Web3()
        acc = w3.eth.account.create(extra_entropy)

        private_key_file = settings.PRIVATE_KEY_FOLDER / self.id_as_str
        private_key_file.write_text(w3.to_hex(acc.key))

        self.eth_address = acc.address
        self.private_key = self.id_as_str
        self.save(update_fields=['eth_address', 'private_key'])

    @property
    def display(self):
        if self.human_readable is not None and len(self.human_readable) > 0:
            return self.human_readable
        if self.identifier is not None:
            return self.identifier
        return self.id_as_str

    @staticmethod
    def get_or_create_remote_user(identifier, human_readable, identity, eth_address):
        p = Profile.objects.filter(identifier=identifier)
        if not p.exists():
            p = Profile.objects.create(identifier=identifier, identity=identity, eth_address=eth_address)
        else:
            p = p.first()
        if p.human_readable != human_readable:
            p.human_readable = human_readable
            p.save(update_fields=['human_readable'])

        return p

    @staticmethod
    # deprecated. do not use.
    def create_user(identifier: str, common_name: str, address: str) -> "Profile":
        qs = User.objects.filter(username=identifier)
        if qs.exists():
            return qs.first().profile
        # TODO check if a suitable node exists and set the node
        user = User.objects.create(username=identifier)
        user.profile.identifier = identifier
        user.profile.save()
        return user.profile

    @staticmethod
    def import_profile(**kwargs):
        logging.info('Creating or updating a user profile via broadcast.')
        # inbox_message = kwargs.get('inbox_message')
        message: Message = kwargs.get('message')
        content: ProfileMessageContent = ProfileMessageContent(**message.object.content)
        if message.type == 'create':
            p = Profile.get_or_create_remote_user(content.identifier, content.human_readable, content.identity, content.eth_address)
            p.node = Node.objects.get_by_identifier(message.from_)

        if message.type == 'update':
            qs = Profile.objects.filter(identifier=content.identifier)
            if not qs.exists():
                logging.warning('Profile with identifier %s can not be updated because is does not exist.')
                return

            p = qs.first()
            p.human_readable = content.human_readable

        # only create and update exist
        p.organization = content.organization
        p.eth_address = content.eth_address
        if content.data is not None:
            p.orcid = content.data.get('orcid')
            p.pubmed = content.data.get('pubmed')
            p.google_scholar = content.data.get('google_scholar')
        p.save()

    def as_token(self) -> str:
        data = UserMessage(content=UserMessageContent(identifier=settings.IDENTIFIER,
                                                      common_name=settings.COMMON_NAME,
                                                      did=settings.ORGANIZATION_DID,
                                                      address=settings.ADDRESS,
                                                      node_name=settings.NODE_NAME,
                                                      cdn_address=settings.CDN_ADDRESS,
                                                      certificate_thumbprint=config.CERTIFICATE_THUMBPRINT))
        token = token_utils.create_token('Node', f'Node {settings.IDENTIFIER}', data.dict())
        return token

    @staticmethod
    def get_hub_profile():
        return Profile.objects.create_and_return(identifier.from_string(settings.HUB_IDENTIFIER))

    def get_api_key(self):
        token, _ = Token.objects.update_or_create(user=self.user)
        return token.key

    def identifier_as_common_name(self):
        pass

    def update_user_in_registry(self):
        assert self.is_published
        from apps.federation.outbox.models import OutboxMessage

        msg = ProfileMessage(content=ProfileMessageContent(
            human_readable=self.human_readable,
            organization=self.organization,
            identifier=self.identifier,
            identity=self.identity,
            eth_address=self.eth_address,
            data={
                'orcid': self.orcid,
                'pubmed': self.pubmed,
                'google_scholar': self.google_scholar
            }
        ))

        OutboxMessage.create(sender=self, recipient=None, message_object=msg,
                             message_type=UpdateMessage).send()

    def publish_in_registry(self):
        from apps.federation.outbox.models import OutboxMessage

        msg = ProfileMessage(content=ProfileMessageContent(
            human_readable=self.human_readable,
            organization=self.organization,
            identifier=self.identifier,
            identity=self.identity,
            eth_address=self.eth_address,
            data={
                'orcid': self.orcid,
                'pubmed': self.pubmed,
                'google_scholar': self.google_scholar
            }
        ))

        OutboxMessage.create(sender=self, recipient=None, message_object=msg).send(send_async=False)
        # set any value here to keep the rest of the logic working
        self.is_published = True
        self.save(update_fields=['is_published'])

        msg = CreateMessage(
            object=Object(model="user", value=self.to_identifiable()),
            actor=self.to_actor(),
            context={}
        )
        from apps.blockchain.models import Log
        Log.send_broadcast(msg)

    def publish_to_registry(self):
        if not self.is_published:
            self.publish_in_registry()
        else:
            self.update_user_in_registry()

    def to_actor(self):
        return Actor(organization=self.organization, identifier=self.identifier, display=self.display, model="user")

    def to_identifiable(self):
        return Identifiable(model="user", display=self.human_readable, identifier=self.identifier)
