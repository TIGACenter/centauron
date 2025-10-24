from __future__ import annotations

import logging
from importlib import import_module
from typing import TYPE_CHECKING

import httpx
from django.conf import settings
from httpx import Response
from tenacity import retry, stop_after_attempt, wait_exponential

from apps.blockchain.tasks import send_private_message, send_broadcast_message_wrapper
from apps.dsf.client import send_bundle, send, update
from apps.dsf.tasks import create_bundle, create_bundle_for_questionnaire
from apps.federation.inbox.utils import send_message_to_inbox
from apps.federation.outbox.exceptions import MessageSendException

if TYPE_CHECKING:
    from apps.federation.outbox.models import OutboxMessage


# backend and adapter pattern: https://charlesleifer.com/blog/django-patterns-pluggable-backends/

def get_backend():
    package, klass = settings.DECENTRALIZED_BACKEND.rsplit('.', 1)
    # dynamically import the module, in this case app.backends.adapter_a
    module = import_module(package)
    # pull the class off the module and return
    adapter = getattr(module, klass)()
    return MessageBackend(adapter)


def get_broadcast_backend():
    package, klass = settings.BROADCAST_BACKEND.rsplit('.', 1)
    # dynamically import the module, in this case app.backends.adapter_a
    module = import_module(package)
    # pull the class off the module and return
    adapter = getattr(module, klass)()
    return MessageBackend(adapter)


class MessageBackend(object):

    def __init__(self, adapter):
        self.adapter = adapter

    def send_message(self, outbox_message: OutboxMessage):
        logging.info(f"USING ADAPTER {self.adapter}")
        try:
            if outbox_message.is_broadcast:
                logging.info('Sending broadcast message.')
            else:
                logging.info('Sending message to %s @ %s', outbox_message.recipient, outbox_message.recipient.node)
            outbox_message.processing = True
            outbox_message.save(update_fields=['processing'])
            response: Response = self.adapter.send_message(outbox_message)
            # response can be None if sending a message via firefly adapter and Besu as broadcast
            if response is not None:
                outbox_message.status_code = response.status_code
                outbox_message.response_body = response.text

            outbox_message.processing = False
            outbox_message.processed = True
        except MessageSendException as e:
            logging.exception(e)
            logging.error('Request to %s yields to status code %s', e.address, e.status_code)
            # logging.error(response.content)
            outbox_message.processing = False
            outbox_message.processed = False
            outbox_message.status_code = e.response.status_code
            outbox_message.error = e.error
            outbox_message.response_body = e.response.text
        finally:
            outbox_message.save(update_fields=['processing', 'processed', 'status_code', 'response_body', 'error'])


class BaseAdapter:
    def __init__(self):
        self.backend = self.get_backend()

    def get_backend(self):
        raise NotImplementedError()

    def send_message(self, outbox_message) -> Response:
        raise NotImplementedError()


class DSFAdapter(BaseAdapter):

    def get_backend(self):
        return DSFBackend()

    def send_message(self, outbox_message):
        return self.backend.send_message(outbox_message)


class CentauronAdapter(BaseAdapter):

    def get_backend(self):
        return CentauronBackend()

    def send_message(self, outbox_message: OutboxMessage):
        return self.backend.send_message(outbox_message)


class FireflyAdapter(BaseAdapter):

    def get_backend(self):
        return FireflyBackend()

    def send_message(self, outbox_message: OutboxMessage):
        return self.backend.send_message(outbox_message)


class DSFBackend:

    def send_message(self, outbox_message: 'OutboxMessage'):
        resource = outbox_message.extra_data.get('resource', None)
        input = outbox_message.extra_data.get('input', None)
        assert resource in ['task', 'questionnaireresponse']
        if input is None:
            input = []
        # assert input is not None
        target_organization_identifier = outbox_message.recipient.node.identifier
        # TODO how to specify to which user this message belongs to???

        if resource == 'task':
            process = outbox_message.extra_data.get('process')
            message_name = outbox_message.extra_data.get('message_name')
            profile = outbox_message.extra_data.get('profile')
            business_key = outbox_message.extra_data.get('business_key')
            assert process is not None
            assert message_name is not None
            assert profile is not None
            import json
            bundle = create_bundle(process=process,
                                   message_name=message_name,
                                   profile=profile,
                                   input=input,
                                   business_key=business_key,
                                   message=json.dumps(outbox_message.message),
                                   target_organization_identifier=target_organization_identifier)
            return send_bundle(bundle)

        if resource == 'questionnaireresponse':
            url = outbox_message.extra_data.get('url')
            assert url is not None
            qr, binary = create_bundle_for_questionnaire(url, target_organization_identifier, input)
            b = send(f'{settings.FHIR_SERVER}Binary', binary).json()
            items = qr['item']
            for i in items:
                linkId = i['linkId']
                if linkId == 'message':
                    i['answer'][0]['valueString'] = f'Binary/{b["id"]}'
            return update(f'{settings.FHIR_SERVER}QuestionnaireResponse/{qr["id"]}', qr)


class CentauronBackend:

    def send_message(self, message: OutboxMessage):
        headers = {'accept': 'application/json', 'content-type': 'application/json'}
        # if settings.DEBUG:
        #     headers.update(settings.MY_DEV_CREDENTIALS(message.sender.authentication.common_name))
        json = message.message
        cert_file = settings.DSF_CERTIFICATE
        key_file = settings.DSF_CERTIFICATE_PRIVATE_KEY
        url = message.recipient.node.api_address
        return self._send(url, json, headers, cert_file, key_file)

    @retry(
        stop=stop_after_attempt(5),  # Retry up to 5 times
        wait=wait_exponential(multiplier=1, max=60)  # Wait fixed intervals (300/5 seconds = 60 seconds)
    )
    def _send(self, url, json, headers, cert_file, key_file):
        with httpx.Client(verify=settings.VERIFY_TLS, cert=(cert_file, key_file)) as client:
            response = client.post(url,
                                   json=json,
                                   headers=headers,
                                   timeout=30)
            response.raise_for_status()
        if response.status_code != 201:
            raise MessageSendException(url, response.status_code, response.text, response)
        return response

class LocalBackend:

    def send_message(self, message: OutboxMessage):
        recipient = message.recipient
        sender = message.sender

        if recipient.node_id != sender.node_id:
            logging.warning('[LocalBackend] Sender node is not the same as recipient node.')
            return

        send_message_to_inbox(message.message)


class FireflyBackend:

    def send_message(self, message: OutboxMessage):
        recipient = message.recipient
        if not message.is_broadcast:
            response = send_private_message(sender=message.sender.identity,
                                            topic=settings.FIREFLY_MESSAGE_TOPIC_DATA_TRANSFER,
                                            data=message.message,
                                            recipient_dids=recipient.node.did,
                                            # FIXME better would be using recipient.identity but somehow it does not work after a while in firefly,
                                            send_async=False)
        else:
            response = send_broadcast_message_wrapper(sender=message.sender.identity,
                                                      topic=settings.FIREFLY_MESSAGE_TOPIC_DATA_TRANSFER,
                                                      data=message.message)
        return response
