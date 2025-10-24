from celery import shared_task
from django.conf import settings

from apps.federation.federation_invitation import cca_utils
from apps.federation.federation_invitation.models import FederationInvitation


@shared_task
def send_federation_invitation(invite_pk, project_data):
    invite = FederationInvitation.objects.get(pk=invite_pk)

    url = f'{settings.CCA_URL}invitations/create/'
    payload = {'invitee': invite.from_identifier,
               'inviter': invite.to.identifier,
               'project_data': project_data}
    response = cca_utils.post(url, payload)

    if response == None:
        return

    invite_remote_id = response.json()['id']
    invite.remote_invite_id = invite_remote_id
    invite.save(update_fields=['remote_invite_id'])
