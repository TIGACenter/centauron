import logging
import typing
from typing import Any

from django.conf import settings
from django.db import models

from apps.core.models import Base
from apps.federation.models import Message
from apps.node.models import Node
from apps.project.models import Project
from apps.user.user_profile.models import Profile


class InboxMessage(Message):
    # business key for correlation
    business_key = models.CharField(max_length=100, blank=True, null=True, default=None)

    def save(self, *args, **kwargs):
        self.box = Message.Box.INBOX
        return super(InboxMessage, self).save(*args, **kwargs)

    @staticmethod
    def get_model(model):
        from apps.share.models import Share
        from apps.challenge.challenge_submission.models import Submission
        from apps.challenge.challenge_leaderboard.models import LeaderboardEntry
        from apps.project.project_ground_truth.models import GroundTruthSchema

        '''
        Returns a tuple (method reference, kwargs) for the method that processes a message for a specific model
        '''
        lookup = {
            # 'user': (ProfileData.import_user, {}),
            'profile': (Profile.import_profile, {}),
            'node': (Node.import_node, {'current_user': None}),
            'share': (Share.import_share, {}),
            'retract-share': (Share.retract_share, {}),
            'submission': (Submission.import_submission, {}),
            'submission-result': (Submission.import_submission_result, {}),
            'leaderboard': (LeaderboardEntry.import_leaderboard, {}),
            'project-invitation': (Project.import_project_invitation, {}),
            'project-invitation-response': (Project.process_invitation_response, {}),
            'project': (Project.import_project, {}),
            'ground-truth-schema': (GroundTruthSchema.import_ground_truth, {}),
        }

        default = (InboxMessage.process_message, {})
        return lookup.get(model, default)

    @staticmethod
    def process_message(**kwargs):
        # TODO extract this method into a MessageRouter class?
        persisted_message: InboxMessage = kwargs.get('message', None)
        message: typing.Dict[str, Any] = kwargs.get('parsed_message', None)
        message_type = message['object']['type']
        application = message['object'].get('application', None)
        key = application if application is not None else message_type
        if key is None:
            logging.error('No application specified for message %s.', persisted_message.id_as_str)
            return

        destination_url = settings.MESSAGE_APPLICATION.get(key, None) + 'api/inbox/'

        if destination_url is None:
            logging.error('No application defined for message type %s', message_type)
            return
