import json
import logging
from typing import Dict, Any

import httpx
import rel
import websocket
from django.conf import settings

from apps.blockchain.messages import ShareMessage, UseMessage, AddMessage, CreateMessage, TestMessage, UnknownMessage
from apps.federation.inbox.utils import send_message_to_inbox
from apps.federation.messages import Message
from apps.node.models import Node
from apps.user.user_profile.models import Profile


def ack_event(ws, id: str):
    msg = {"type": "ack", "id": id}
    logging.debug("Acking message with id %s", id)
    ws.send(json.dumps(msg))
    logging.debug("Acking done")


def message_is_allowed(message) -> bool:
    # do not filter broadcasts
    if message.get('to') is None:
        return True

    object = message.get('object')
    if object is None:
        return True

    recipient = object.get('recipient')
    sender = object.get('sender')

    type = object.get('type')
    # a project invite can always be received
    if type == 'project-invitation':
        return True

    p = Profile.objects.get(identifier=recipient)
    qs = p.communication_allowed_with_users.filter(identifier=sender)
    return qs.exists()


def on_message(ws, block:'Block'):
    logging.info("Receiving message.")

    try:
        if block.is_broadcast:
            try:
                process_message(block, block.content_as_json)
            except Exception as e:
                logging.exception(e)
        # send message to inbox to proceed with message receiving workflow
        elif block.is_data_transfer:
            msg = block.content

            # ignore broadcast messages that are sent from the current node
            if msg.get('from') == settings.IDENTIFIER and msg.get('to') is None:
                logging.debug('Ignoring broadcast message from this node.')
                return

            if not message_is_allowed(msg):
                logging.info('Ignoring message from another user that is not on allow list of recipient.')
                return

            # node announce message cannot be imported via normal flow because it has no sender
            if msg.get('to') is None and msg.get('from') is not None and msg.get('object').get(
                'type') == 'node' and msg.get('type') == 'create':
                Node.import_node(current_user=None, message=msg)
                return

            # import a newly published user
            if msg.get('to') is None and msg.get('from') is not None and msg.get('object').get(
                'type') == 'profile' and msg.get('type') == 'create':
                Profile.import_profile(message=Message(**msg))
                return

            status_code = send_message_to_inbox(msg)
            logging.info('Status Code: %s', status_code)
    except Exception as e:
        logging.exception(e)


def on_error(ws, error):
    logging.error("Error: [%s]", error)


def on_close(ws, close_status_code, close_msg):
    logging.info("Websocket closed with status code %s and message [%s]", close_status_code, close_msg), close_msg


def on_open(ws):
    logging.info("Opening websocket.")


def download_message(message_id: str):
    url = f'{settings.FIREFLY_API_URL}namespaces/{settings.FIREFLY_NAMESPACE}/messages/{message_id}/data'
    logging.debug("Downloading message from %s", url)
    response = httpx.get(url)
    return response.json()


def process_message(message: 'Block', data: Dict[str, Any]):
    for data in data.get('data', []):
        value = data.get('value')
        if value is None:
            continue
        action = value.get('action')
        logging.info("Processing message with action %s", action)
        if action == 'share':
            model = ShareMessage
        elif action == 'use':
            model = UseMessage
        elif action == 'add':
            model = AddMessage
        elif action == 'create':
            model = CreateMessage
        elif action == 'test':
            model = TestMessage
        else:
            model = UnknownMessage
            logging.error("No model found for action %s", action)

        try:
            parsed = model.model_validate(value)
            from apps.blockchain.models import Log

            # do not store duplicated messages in case of a restart of the listener
            if not Log.objects.filter(event_id=message.event_id, message_id=message.event_id).exists():
                Log.from_message(parsed, message, data)
            else:
                logging.info('Ignoring message as it is already persisted.')
        except Exception as e:
            logging.exception(e)
            raise Exception(e)


def run_client():
    logging.info("Connecting to websocket at %s", settings.FIREFLY_WS_URL)
    websocket.enableTrace(True)
    ws = websocket.WebSocketApp(settings.FIREFLY_WS_URL,
                                on_open=on_open,
                                on_message=on_message,
                                on_close=on_close,
                                on_error=on_error)
    ws.run_forever(dispatcher=rel, reconnect=5)
    rel.signal(2, rel.abort)
    rel.dispatch()
