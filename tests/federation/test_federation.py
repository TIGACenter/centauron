import json
import uuid

import httpx
import pytest
from django.urls import reverse

from apps.federation.messages import UserMessage, UserMessageContent, ProjectObject, Message, ProjectInvitationObject, \
    ProjectInviteAcceptMessage, ProjectMessageContent
from apps.federation.outbox.models import OutboxMessage
from apps.federation.outbox.tasks import send_outbox_message
from apps.node.models import Node
from apps.share.share_token import token_utils
from apps.utils import get_node_origin


@pytest.mark.django_db
def test_add_node(setup, client, user, settings, respx_mock):
    settings.IDENTIFIER = uuid.uuid4().hex
    settings.NODE_NAME = uuid.uuid4().hex
    settings.ADDRESS = uuid.uuid4().hex
    settings.CERTIFICATE_THUMBPRINT = uuid.uuid4().hex
    settings.FHIR_SERVER = f'http://{uuid.uuid4().hex}.com/'
    url = reverse('federation:add-node')
    # test for error
    respx_mock.post(settings.FHIR_SERVER).mock(return_value=httpx.Response(400))
    data = UserMessage(content=UserMessageContent(identifier=settings.IDENTIFIER,
                                                  common_name=settings.IDENTIFIER,
                                                  address=settings.ADDRESS,
                                                  node_name=settings.NODE_NAME,
                                                  did=settings.ORGANIZATION_DID,
                                                  cdn_address=settings.CDN_ADDRESS,
                                                  certificate_thumbprint=settings.CERTIFICATE_THUMBPRINT))
    code = token_utils.create_token('Node', f'Node {settings.IDENTIFIER}', data.dict())
    R = client.post(url, {'code': code})
    assert R.status_code == 302
    assert Node.objects.count() == 1
    qs = Node.objects.filter(identifier=settings.IDENTIFIER)
    assert qs.count() == 0
    # test for success
    respx_mock.post(settings.FHIR_SERVER).mock(return_value=httpx.Response(200))
    data = UserMessage(content=UserMessageContent(identifier=settings.IDENTIFIER,
                                                  common_name=settings.IDENTIFIER,
                                                  address=settings.ADDRESS,
                                                  node_name=settings.NODE_NAME,
                                                  certificate_thumbprint=settings.CERTIFICATE_THUMBPRINT))
    code = token_utils.create_token('Node', f'Node {settings.IDENTIFIER}', data.dict())
    R = client.post(url, {'code': code})
    assert R.status_code == 302
    assert Node.objects.count() == 2
    qs = Node.objects.filter(identifier=settings.IDENTIFIER)
    assert qs.count() == 1
    node = qs.first()
    assert node.human_readable == settings.NODE_NAME
    assert node.address_fhir_server == settings.FHIR_SERVER
    assert node.address_centauron == settings.ADDRESS


@pytest.mark.django_db
def test_send_outbox_message_task(setup, project, settings, respx_mock):
    settings.FHIR_SERVER = f'http://{uuid.uuid4()}.com/'
    respx_mock.post(settings.FHIR_SERVER + 'Task/').mock(return_value=httpx.Response(status_code=201))

    n2 = Node.objects.create(identifier=f'{uuid.uuid4()}.test.com')
    project.add_member(n2)
    om = OutboxMessage.objects.first()

    send_outbox_message(om.id_as_str)

    om1 = OutboxMessage.objects.first()

    assert om.pk == om1.pk
    assert om1.processed
    assert not om1.processing
    assert om1.recipient == n2
    assert om1.sender == get_node_origin()
    assert om1.status_code is None
    assert om1.error is None


@pytest.mark.django_db
def test_send_outbox_message_assertions(setup, project, settings, respx_mock):
    settings.FHIR_SERVER = f'http://{uuid.uuid4()}.com/'
    settings.DECENTRALIZED_BACKEND = 'apps.federation.outbox.backends.DSFBackend'

    respx_mock.post(settings.FHIR_SERVER + 'QuestionnaireResponse/').mock(return_value=httpx.Response(status_code=201))
    n2 = Node.objects.create(identifier=f'{uuid.uuid4()}.test.com')

    def om(extra_data):
        mo = ProjectObject(content=project.to_message_object())
        om = OutboxMessage.create(recipient=n2, message_object=mo, extra_data=extra_data)
        with pytest.raises(Exception):
            send_outbox_message(om.id_as_str)

    om({})
    om({'resource': 'abc'})
    om({'resource': 'task'})
    om({'resource': 'task', 'method': 'put'})
    om({'resource': 'task', 'method': 'post', 'process': uuid.uuid4().hex})
    om({'resource': 'questionnaireresponse', 'method': 'post', 'process': uuid.uuid4().hex,
        'message_name': uuid.uuid4().hex,
        'profile': uuid.uuid4().hex, 'input': []
        })
    om({'resource': 'questionnaireresponse', 'method': 'post', 'process': uuid.uuid4().hex,
        'message_name': uuid.uuid4().hex,
        'profile': uuid.uuid4().hex, 'url': uuid.uuid4().hex, 'input': []
        })


@pytest.mark.django_db
def test_send_outbox_message_questionnaire_response(setup, project, settings, respx_mock):
    settings.FHIR_SERVER = f'http://{uuid.uuid4()}.com/'
    settings.DECENTRALIZED_BACKEND = 'apps.federation.outbox.backends.DSFBackend'

    respx_mock.post(settings.FHIR_SERVER + 'QuestionnaireResponse/').mock(return_value=httpx.Response(status_code=201))
    url_questionnaire = f'{settings.FHIR_SERVER}QuestionnaireResponse/{uuid.uuid4()}'

    questionnaire_response_expected = {
                                  "resourceType": "QuestionnaireResponse",
                                  "id": "07e7d9f3-406b-4c57-b232-9684a01428c6",
                                  "meta": {
                                    "versionId": "2",
                                    "lastUpdated": "2023-10-31T09:50:29.623+01:00"
                                  },
                                  "questionnaire": "http://centauron.tiga.com/fhir/Questionnaire/project-invite-accept|1.0",
                                  "status": "completed",
                                  "author": {
                                    "type": "Organization",
                                    "identifier": {
                                      "system": "http://dsf.dev/sid/organization-identifier",
                                      "value": "fhir.ak.dev.centauron.net"
                                    }
                                  },
                                  "item": [ {
                                    "linkId": "business-key",
                                    "text": "The business-key of the process execution",
                                    "answer": [ {
                                      "valueString": "20dbe16b-db2b-48ce-ab4c-0b6a98936248"
                                    } ]
                                  }, {
                                    "linkId": "user-task-id",
                                    "text": "The user-task-id of the process execution",
                                    "answer": [ {
                                      "valueString": "15673"
                                    } ]
                                  }, {
                                    "linkId": "invite-accept",
                                    "text": "Do you accept the invitation to collaborate on the project?",
                                    "answer": [ {
                                      "valueBoolean": True
                                    } ]
                                  } ]
                                }

    respx_mock.put(url_questionnaire, json=questionnaire_response_expected).mock(return_value=httpx.Response(status_code=200))
    respx_mock.get(url_questionnaire).mock(return_value=httpx.Response(status_code=200,
                                                                       text='''
                                                                       {
                                  "resourceType": "QuestionnaireResponse",
                                  "id": "07e7d9f3-406b-4c57-b232-9684a01428c6",
                                  "meta": {
                                    "versionId": "2",
                                    "lastUpdated": "2023-10-31T09:50:29.623+01:00"
                                  },
                                  "questionnaire": "http://centauron.tiga.com/fhir/Questionnaire/project-invite-accept|1.0",
                                  "status": "completed",
                                  "author": {
                                    "type": "Organization",
                                    "identifier": {
                                      "system": "http://dsf.dev/sid/organization-identifier",
                                      "value": "fhir.ak.dev.centauron.net"
                                    }
                                  },
                                  "item": [ {
                                    "linkId": "business-key",
                                    "text": "The business-key of the process execution",
                                    "answer": [ {
                                      "valueString": "20dbe16b-db2b-48ce-ab4c-0b6a98936248"
                                    } ]
                                  }, {
                                    "linkId": "user-task-id",
                                    "text": "The user-task-id of the process execution",
                                    "answer": [ {
                                      "valueString": "15673"
                                    } ]
                                  }, {
                                    "linkId": "invite-accept",
                                    "text": "Do you accept the invitation to collaborate on the project?",
                                    "answer": [ {
                                      "valueBoolean": false
                                    } ]
                                  } ]
                                }'''))
    n2 = Node.objects.create(identifier=f'{uuid.uuid4()}.test.com')

    mo = ProjectObject(content=project.to_message_object())
    extra_data = {'resource': 'questionnaireresponse', 'url': url_questionnaire,
                  'input': {'invite-accept': [{'valueBoolean': True}]}
                  }

    om = OutboxMessage.create(recipient=n2, message_object=mo, extra_data=extra_data)
    send_outbox_message(om.id_as_str)

    om = OutboxMessage.objects.get(pk=om.pk)

    assert om.processed
    assert om.error is None
    assert om.status_code == 200


def test_serialize_deserialize_message():
    to = uuid.uuid4().hex
    from_ = uuid.uuid4().hex
    type = 'create'
    object = ProjectObject(content=[ProjectMessageContent(id='', identifier='', name='', origin='')])
    msg = Message(to=to, from_=from_, type=type, object=object)
    j = msg.json(by_alias=True)
    print(j)
    j = json.loads(j)
    msg2 = Message(**j)
    assert msg2.to == to
    assert msg2.from_ == from_
