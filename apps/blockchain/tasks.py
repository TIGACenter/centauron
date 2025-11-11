import io
import json
import logging
import uuid
from typing import Any, Dict

import httpx
from celery.app import shared_task
from django.conf import settings



@shared_task
def send_broadcast_message(sender, payload):
    from apps.user.user_profile.models import Profile
    try:
        sender = Profile.objects.get(identity=sender)
        return _send_message(sender, payload)
    except Profile.DoesNotExist:
        logging.error(f"Profile with identity {sender} does not exist. Cannot send broadcast message.")
        return

def store_string_in_ipfs(payload:Dict[str, Any]):
    url = f'{settings.IPFS_URL}api/v0/add'
    s = json.dumps(payload)
    string_bytes = s.encode("utf-8")
    # content_size = len(string_bytes)
    string_stream = io.BytesIO(string_bytes)
    files = {
        'file': (f"{uuid.uuid4()}.json", string_stream) # Pass the stream object here
    }

    r = httpx.post(url, files=files)
    return r.json()

@shared_task
def _send_message(sender:'Profile', payload:Dict[str,Any]):

    if sender.private_key is None:
        logging.error(f"Profile {sender.identity} has no private key.")
        return

    d = store_string_in_ipfs(payload)

    tx_input = json.dumps({'type': 'broadcast', 'cid': d['Hash']})
    private_key = sender.get_private_key()
    from apps.blockchain.backends import get_adapter

    get_adapter()().write_tx(None, private_key, tx_input)


def _build_payload(topic, data, sender):
    if not isinstance(topic, list):
        topic = [topic]
    data_ = {
        "header": {
            "topics": topic,
        },
        "data": [{
            "validator": "json",
            "value": data
        }]
    }
    # if sender is not None:
    #     data_['header']['author'] = sender
    return data_


def send_broadcast_message_wrapper(topic, data, send_async=False, sender=None):
    if sender is None:
        sender = settings.ORGANIZATION_DID
    payload = _build_payload(topic, data, sender)
    if send_async:
        send_broadcast_message.delay(sender, payload)
    else:
        return send_broadcast_message(sender, payload)


def send_private_message(topic, data, recipient_dids: list[str] | str, send_async: bool = True, sender=None):
    payload = _build_payload(topic, data, sender)
    if not isinstance(recipient_dids, list):
        recipient_dids = [recipient_dids]

    payload['group'] = {
        'members': [{'identity': i for i in recipient_dids}],
    }

    url = f'{settings.FIREFLY_API_URL}namespaces/{settings.FIREFLY_NAMESPACE}/messages/private'
    if send_async:
        _send_message.delay(url, payload)
    else:
        return _send_message(url, payload)
