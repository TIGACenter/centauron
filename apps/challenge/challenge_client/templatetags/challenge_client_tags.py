from django import template

from apps.challenge.challenge_client.models import ChallengeParticipantApproval

register = template.Library()


@register.filter
def execution_for_submission(executions, submission):
    return executions

@register.filter
def execution_for_definition(definition, executions):
    return executions.filter(definition=definition)

@register.simple_tag
def is_enrolled(request, challenge):
    if not request.user.is_authenticated:
        return False
    return ChallengeParticipantApproval.objects.filter(
        challenge_participants__challenge=challenge,
        profile=request.user.profile,
        approved=True).exists()
