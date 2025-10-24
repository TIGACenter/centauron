import logging
from functools import partial

from django.conf import settings
from django.db import transaction
from django.http import JsonResponse
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.federation.inbox import tasks
from apps.federation.inbox.models import InboxMessage
from apps.user.user_profile.models import Profile


class InboxView(APIView):
    def post(self, request):
        data = request.data
        business_key = request.META.get('HTTP_X_BUSINESS_KEY')

        # TODO do some validation
        # TODO use message object here
        recipient = data.get('to', None)
        sender = data.get('from', None)
        object = data.get('object', None)
        identifier_recipient = object.get('recipient')
        identifier_sender = object.get('sender')
        user_recipient = None
        logging.info('Receiving message from [%s] to [%s]', identifier_sender, identifier_recipient)
        try:
            if identifier_recipient is not None:
                user_recipient = Profile.objects.get(identifier=identifier_recipient, node__identifier=recipient)
            # for user publish message the user will not be found here. that is why this message is handled in blockchain listener.
            user_sender = Profile.objects.get(identifier=identifier_sender, node__identifier=sender)
        except Profile.DoesNotExist as e:
            logging.error('User recipient or sender does not exist on this server.')
            logging.exception(e)
            return JsonResponse(status=status.HTTP_404_NOT_FOUND,
                                data={'message': 'User recipient or sender not found.'})

        message = InboxMessage.objects.create(message=data,
                                              recipient=user_recipient,
                                              sender=user_sender,
                                              business_key=business_key)
        transaction.on_commit(partial(tasks.process_inbox_message.delay, message.id_as_str))

        message_location = request.build_absolute_uri(f'/message/{message.id_as_str}')
        if not settings.DEBUG:  # the other side needs https instead of http for message correlation
            message_location = message_location.replace('http://', 'https://')
        return Response(status=status.HTTP_201_CREATED,
                        headers={'Location': message_location})
