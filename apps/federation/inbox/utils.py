import logging

import httpx
from django.conf import settings
from django.urls import reverse
from rest_framework.authtoken.models import Token

from apps.utils import get_user_node


def send_message_to_inbox(payload):
    # cut the last / from the external address. the / is the prefix of the reverse
    url = settings.EXTERNAL_ADDRESS[:-1] + reverse('inbox')
    # get a token from drf
    token, _ = Token.objects.get_or_create(user=get_user_node().user)
    response = httpx.post(url, json=payload, headers={'Authorization': f'Token {token.key}'})
    if response.status_code != 201:
        logging.error('Failed to send message to internal inbox. response code: [%s] response: [%s]',
                      response.status_code, response.text)
    return response.status_code
