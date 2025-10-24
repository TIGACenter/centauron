from datetime import datetime

from django.db import models
from django.utils import timezone

from apps.core import identifier
from apps.core.models import Base, IdentifieableMixin
from apps.dsf import constants
from apps.federation.messages import ShareObject
from apps.federation.outbox.models import OutboxMessage
from apps.node.models import Node
from apps.share.models import Share
from apps.share.share_token import token_utils
from apps.user.user_profile.models import Profile


class ShareToken(IdentifieableMixin, Base):
    class Permission(models.TextChoices):
        VIEW = "view"
        TRANSFER = "transfer"
        METADATA = "metadata"
        DOWNLOAD = "download"

    # token = models.CharField(max_length=1000, default=utils.generate_token)
    share = models.ForeignKey("share.Share", null=False, on_delete=models.CASCADE, related_name="tokens")
    valid_from = models.DateTimeField(null=False)
    valid_until = models.DateTimeField(null=False)
    # permissions are handled on an object-level instead of share-level
    # permissions = ArrayField(models.CharField(max_length=20, null=True, choices=Permission.choices, default=None))

    """
    The receiver of this ShareToken.
    """
    recipient = models.ForeignKey('user_profile.Profile', on_delete=models.CASCADE, related_name="share_tokens")

    # TODO use CreatedByMixin
    created_by = models.ForeignKey('user_profile.Profile', on_delete=models.SET_NULL, null=True,
                                   related_name="created_share_tokens")
    # this is the identifier of the project this share belongs to.
    project_identifier = models.CharField(default=None, null=True, max_length=200)

    @staticmethod
    def parse(text):
        """
        Parse a share token shareable text.
        :param text: the textual representation of a ShareToken.
        :return: the created ShareToken instance. Not persisted yet.
        """
        data = token_utils.parse_token(text)
        profile = Profile(identifier=data["profile"]["identifier"])
        return ShareToken(
            valid_until=datetime.fromisoformat(data["valid_until"]),
            valid_from=datetime.fromisoformat(data["valid_from"]),
            permissions=data["permissions"],
            token=data["token"],
            share=Share(
                name=data["share"]["name"],
                original_share_pk=data["share"]["pk"],
                blinded=data["share"].get("blinded", False),
            ),
            profile=profile,
        )

    def is_valid(self):
        return self.valid_from <= timezone.now() <= self.valid_until

    def clean(self):
        if self.valid_until < self.valid_from:
            raise ValueError(f"{self.valid_until} cannot be smaller than {self.valid_from}.")

    # def has_permission(self, perm):
    #     return perm in self.permissions

    class Invalid(Exception):
        """
        Is thrown if a parsed ShareToken is invalid.
        """

        def __init__(self, *args):
            super().__init__(*args)

    def send_to_node(self):
        data = self.share.content
        message_object = ShareObject(content=data)
        om = OutboxMessage.create(recipient=self.recipient,
                                  sender=self.created_by,
                                  message_object=message_object)
        om.extra_data = dict(
            resource='task',
            method='post',
            process=constants.PROCESS_MESSAGE_SEND,
            message_name=constants.PROCESS_MESSAGE_SEND_MESSAGE_NAME,
            profile=constants.PROCESS_MESSAGE_SEND_TASK_PROFILE,
            input=[])
        om.save(update_fields=['extra_data'])
        om.send()

    @staticmethod
    def create(*, share: Share,
               # permissions: list[ShareToken.Permission],
               recipient: Profile,
               created_by: Profile,
               valid_from=datetime,
               valid_until: datetime):
        return ShareToken.objects.create(share=share,
                                         # permissions=permissions,
                                         valid_from=valid_from,
                                         valid_until=valid_until,
                                         recipient=recipient,
                                         created_by=created_by,
                                         identifier=identifier.create_random('share_token'))
