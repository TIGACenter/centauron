import logging

import httpx
from django.conf import settings

from apps.dsf.exceptions import DSFException

cert = (settings.DSF_CERTIFICATE, settings.DSF_CERTIFICATE_PRIVATE_KEY)
headers = {'Accept': 'application/json+fhir'}


def send_task(task):
    url = f'{settings.FHIR_SERVER}Task/'
    return send(url, task)


def send_bundle(bundle):
    url = f'{settings.FHIR_SERVER}/'
    response = _send(url, bundle)
    if response.status_code != 200:
        raise DSFException(response.text)
    return response


def send_questionnaire_response():
    pass


def send(url, payload):
    response = _send(url, payload)
    logging.info(f'{response.status_code}, {response.text}')
    if response.status_code != 201:
        raise DSFException(response.text)
    return response


def _send(url, payload):
    logging.info('Posting FHIR resource.')
    response = httpx.post(url, json=payload, cert=cert, headers=headers)
    logging.info(f'{response.status_code}')
    return response


def update(url, payload):
    logging.info('Update FHIR resource.')
    response = httpx.put(url, json=payload, cert=cert, headers=headers)
    logging.info(f'{response.status_code}, {response.text}')

    if response.status_code != 200:
        raise DSFException(response.text)
    return response


def get_project_invites():
    url = f'{settings.FHIR_SERVER}QuestionnaireResponse/?status=in-progress&questionnaire=http://centauron.net/fhir/Questionnaire/project/invite|1.0'
    response = get(url)
    return response.json().get('entry')


def get_tasks():
    url = f'{settings.FHIR_SERVER}Task?_profile=http://centauron.net/fhir/StructureDefinition/project/task-invite-response|1.0&status=in-progress'
    return get(url).json().get('entry')


def get_task_by_business_key(business_key):
    tasks = get_tasks()
    for t in tasks:
        r = t['resource']
        for i in r['input']:
            if i['type']['coding'][0]['code'] == 'business-key' and i['valueString'] == business_key:
                return t
    return None


def get_value_for_coding(codings, system, code, value_key='valueString'):
    for c in codings:
        c0 = c['type']['coding'][0]
        if c0['system'] == system and c0['code'] == code:
            return c.get(value_key, None)
    return None


def _get(url, headers=None):
    kw = {}
    if headers is not None:
        kw['headers'] = headers
    response = httpx.get(url, cert=cert, **kw)
    if response.status_code != 200:
        raise DSFException(response.text)
    return response


def get(url):
    return _get(url, headers)


def get_binary(url):
    return _get(url)


def get_resource_by_identifier(resource: str, identifier: str):
    url = f'{settings.FHIR_SERVER}{resource}/?identifier={identifier}'
    R = get(url).json()
    total = R['total']
    if total == 0:
        return None
    if total > 1:
        return R['entry']
    # return resource directly if only one found.
    return R['entry'][0]['resource']
