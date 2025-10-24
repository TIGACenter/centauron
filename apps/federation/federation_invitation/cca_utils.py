import logging

import httpx
from constance import config
from django.conf import settings


def get_authorization_header():
    return {'Authorization': f'Token {config.CCA_TOKEN}'}


def query_user(query_params):
    url = f'{settings.CCA_URL}users/query/?name__icontains={query_params}'  # &organization__icontains={query_params}'
    logging.info('Querying CCA with %s', url)
    response = httpx.get(url, headers=get_authorization_header(), timeout=30.0)

    if response.status_code != 200:
        logging.error('CCA responded with status code %s', response.status_code)
        return None

    return response.json()


def get(url):
    logging.info('Querying CCA with %s', url)
    response = httpx.get(url, headers=get_authorization_header(), timeout=30.0)

    if response.status_code != 200:
        logging.error('CCA responded with status code %s', response.status_code)
        return None

    return response


def post(url, payload):
    logging.info('Posting at CCA with %s', url)
    response = httpx.post(url, json=payload, headers=get_authorization_header(), timeout=30.0)

    if response.status_code != 200:
        logging.error('CCA responded with status code %s', response.status_code)
        return None

    return response


def put(url, payload):
    logging.info('Putting at CCA with %s', url)
    response = httpx.put(url, json=payload, headers=get_authorization_header(), timeout=30.0)

    if response.status_code != 200:
        logging.error('CCA responded with status code %s', response.status_code)
        return None

    return response
