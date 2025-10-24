import json

from celery import shared_task
from django.conf import settings

from apps.challenge.challenge_leaderboard.serializers import LeaderboardEntrySerializer
from apps.challenge.models import Challenge
from apps.federation.messages import LeaderboardObject, CreateMessage
from apps.federation.outbox.models import OutboxMessage
from apps.user.user_profile.models import Profile


@shared_task
def sent_leaderboard_to_hub(challenge_pk, user_pk):
    '''

    {
        "leaderboard": [
            {
                "challenge": "identifier",
                "position": 1,
                "identifier": "identifier",
                "submission": "identifier",
                "metrics": [
                    {
                        "key": "specificity",
                        "value": 0.1234
                    }
                ]
            }
        ]
    }

    :param challenge_pk:
    :return:
    '''
    profile = Profile.objects.get(pk=user_pk)
    challenge = Challenge.objects.for_user(user=profile).get(pk=challenge_pk)

    package = LeaderboardEntrySerializer(challenge.leaderboard_entries.all(), many=True).data
    content = json.loads(json.dumps(package))

    recipient = Profile.objects.get_by_identifier(settings.CHALLENGE_HUB_USER_IDENTIFIER)

    object = LeaderboardObject(
        content={'leaderboard': content, 'challenge': str(challenge.identifier)},
    )
    OutboxMessage.create(
        sender=profile,
        recipient=recipient,
        message_type=CreateMessage,
        message_object=object,
    ).send()
