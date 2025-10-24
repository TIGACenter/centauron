import base64
import uuid
from typing import Dict, Any

from django.conf import settings
from django.utils import timezone

from apps.dsf import constants
from apps.dsf.client import get


def create_binary(message: str, target_organization_identifier: str, content_type: str) -> Dict[str, Any]:
    data = base64.b64encode(message.encode("utf-8")).decode("ascii")
    return {
        "data": data,
        "meta": {
            "profile": [constants.PROFILE_MESSAGE_BINARY],
            "tag": [
                {
                    "system": "http://dsf.dev/fhir/CodeSystem/read-access-tag",
                    "code": "LOCAL"
                },
                {
                    "extension": [
                        {
                            "valueIdentifier": {
                                "system": "http://dsf.dev/sid/organization-identifier",
                                "value": target_organization_identifier
                            },
                            "url": "http://dsf.dev/fhir/StructureDefinition/extension-read-access-organization"
                        }
                    ],
                    "system": "http://dsf.dev/fhir/CodeSystem/read-access-tag",
                    "code": "ORGANIZATION"
                }
            ]
        },
        "contentType": content_type,
        "resourceType": "Binary"
    }


def create_bundle(process: str, message_name: str, profile: str,
                  input: list[Dict[str, Any]], message: str, target_organization_identifier: str,
                  business_key: str | None = None, content_type: str = 'application/json') -> Dict[str, Any]:
    binary = create_binary(message, target_organization_identifier, content_type)
    uuid_binary = uuid.uuid4()
    input.append({
        "type": {
            "coding": [
                {
                    "system": constants.CODESSYTEM_CENTAURON,
                    "code": constants.CODESSYTEM_CENTAURON_CODE_MESSAGE
                }
            ]
        },
        "valueReference": {
            "reference": f"urn:uuid:{uuid_binary}"
        }
    })
    task = create_task(process, message_name, profile, input, business_key, target_organization_identifier)
    uuid_task = uuid.uuid4()

    bundle = {
        "resourceType": "Bundle",
        "type": "batch",
        "entry": [
            {
                "fullUrl": f"urn:uuid:{uuid_binary}",
                "request": {
                    "url": "Binary",
                    "method": "POST"
                },
                "resource": binary
            },
            {
                "fullUrl": f"urn:uuid:{uuid_task}",
                "request": {
                    "url": "Task",
                    "method": "POST"
                },
                "resource": task
            }

        ]
    }

    return bundle


def create_bundle_for_questionnaire(url: str, target_organization_identifier: str, input: list[Dict[str, Any]]) -> (
    Dict[str, Any], Dict[str, Any]):
    message = input
    binary = create_binary(message, target_organization_identifier, "application/json")
    uuid_binary = uuid.uuid4()
    qr = create_questionnaire_response(url)
    # FIXME use a bundle here. error message for that is right now: "dom-3: If the resource is contained in another resource, it SHALL be referred to from elsewhere in the resource or SHALL refer to the containing resource ( (unmatched: 1))
    # FIXME and I cannot find the error
    # items = qr['item']
    # for i in items:
    #     linkId = i['linkId']
    #     if linkId == 'message':
    #     # inp = data.get(linkId, None)
    #     # if inp is not None:
    #         i['answer'][0]['valueReference']['reference'] = f"urn:uuid:{uuid_binary}"
    return qr, binary
    # uuid_task = uuid.uuid4()
    #
    # bundle = {
    #     "resourceType": "Bundle",
    #     "type": "batch",
    #     "entry": [
    #         {
    #             "fullUrl": f"urn:uuid:{uuid_binary}",
    #             "request": {
    #                 "url": "Binary",
    #                 "method": "POST"
    #             },
    #             "resource": binary
    #         },
    #         {
    #             "fullUrl": f"urn:uuid:{uuid_task}",
    #             "request": {
    #                 "url": f"QuestionnaireResponse/{qr['id']}",
    #                 "method": "PUT"
    #             },
    #             "resource": qr
    #         }
    #
    #     ]
    # }
    #
    # return bundle


def create_task(process: str, message_name: str, profile: str,
                input: list[Dict[str, Any]], business_key: str | None = None, target_organization_identifier=None) -> \
    Dict[str, Any]:
    task = {
        "restriction": {
            "recipient": [
                {
                    "identifier": {
                        "system": constants.IDENTIFIER_ORGANIZATION,
                        "value": settings.IDENTIFIER
                    },
                    "type": "Organization"
                }
            ]
        },
        "resourceType": "Task",
        "instantiatesCanonical": process,  # "http://centauron.tiga.com/bpe/Process/project-invite|#{version}",
        "intent": "order",
        "authoredOn": timezone.now().isoformat(),
        "input": [
            {
                "valueString": message_name,  # "inviteUser",
                "type": {
                    "coding": [
                        {
                            "system": constants.CODE_SYSTEM_BPMN_MESSAGE,
                            "code": "message-name"
                        }
                    ]
                }
            },
        ],
        "meta": {
            "profile": [profile]
        },
        "requester": {
            "identifier": {
                "system": constants.IDENTIFIER_ORGANIZATION,
                "value": settings.IDENTIFIER,
            },
            "type": "Organization"
        },
        "status": "requested"
    }

    if business_key is not None:
        has_business_key = len(list(
            filter(lambda e: e['type']['coding'][0]['code'] == 'business-key', task['input']))) == 1
        if not has_business_key:
            task['input'].append(
                create_task_input_string(business_key, "http://dsf.dev/fhir/CodeSystem/bpmn-message",
                                         "business-key"))

    if message_name in ['sendMessage', 'inviteNode', 'sendMessageUpdate']:
        task['input'].append({
            "valueString": f'{constants.IDENTIFIER_ORGANIZATION}|{target_organization_identifier}',  # "inviteUser",
            "type": {
                "coding": [
                    {
                        "system": constants.CODESSYTEM_CENTAURON,
                        "code": "recipient"
                    }
                ]
            }
        })

    for i in input:
        exists = len(list(filter(lambda e: e['type'] == i['type'], task['input']))) > 0
        if not exists:
            task['input'].append(i)

    return task


def create_task_input_string(value: str, system, code):
    return {
        "valueString": value,
        "type": {
            "coding": [
                {
                    "system": system,  # "http://centauron.tiga.com/fhir/CodeSystem/project-invite",
                    "code": code  # "project-data"
                }
            ]
        }
    }


def create_questionnaire_response(url: str) -> Dict[str, Any]:
    qr = get(url).json()
    qr['status'] = 'completed'
    return qr
