import logging

from django.conf import settings
from django.http import JsonResponse
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.federation.federation_invitation import cca_utils
from apps.federation.federation_invitation.models import FederationInvitation
from apps.user.user_profile.models import Profile


class InvitationAPIView(APIView):
    # authentication_classes = [CertificateAuthentication]
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, **kwargs):
        data = request.data
        user = request.user.username
        if user != settings.CCA_LOCAL_USERNAME:
            logging.error('Provided username is not %s', settings.CCA_LOCAL_USERNAME)
            return Response(status=400)

        from_name = data.get('from_name')
        from_identifier = data.get('from_identifier')
        to_identifier = data.get('to')
        node = data.get('node')
        project_data = data.get('project_data')
        remote_id = data.get('remote_id')

        try:
            to = Profile.objects.get(identifier=to_identifier)
        except Profile.DoesNotExist:
            logging.error('Invitation recipient does not exist with identifier [%s]', to_identifier)
            return Response(status=400)

        FederationInvitation.objects.create(
            from_name=from_name,
            from_identifier=from_identifier,
            to=to,
            node_data=node,
            project_data=project_data,
            remote_invite_id=remote_id
        )

        return Response(status=200)


class InvitationUpdateView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def put(self, request, **kwargs):
        data = request.data
        user = request.user.username
        if user != settings.CCA_LOCAL_USERNAME:
            logging.error('Provided username is not %s', settings.CCA_LOCAL_USERNAME)
            return Response(status=400)

        invite = get_object_or_404(FederationInvitation, remote_invite_id=data.get('id'))

        status = data.get('status')
        if status == 'accepted':
            new_status = FederationInvitation.Status.ACCEPTED
        else:
            new_status = FederationInvitation.Status.DECLINED

        invite.status = new_status
        invite.save()

        return Response(status=200)
