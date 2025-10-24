from annoying.fields import AutoOneToOneField
from django.db import models

from apps.challenge.models import Challenge
from apps.core.models import Base
from apps.user.user_profile.models import Profile


class ChallengeParticipants(Base):
    """
    All participants that are enrolled in this challenge.
    """
    challenge = AutoOneToOneField(Challenge, related_name='participants',on_delete=models.CASCADE)
    profiles = models.ManyToManyField(Profile, related_name='participating_in', through='ChallengeParticipantApproval')




class ChallengeParticipantApproval(Base):
    """
    Tracks explicit approval for participants before they can join a challenge.
    """
    challenge_participants = models.ForeignKey(ChallengeParticipants, on_delete=models.CASCADE, related_name="participant_approvals")
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="challenge_approvals")
    approved = models.BooleanField(default=False)  # Admin must set this to True for participation

    class Meta:
        unique_together = ('challenge_participants', 'profile')  # A user can only request approval once per challenge
