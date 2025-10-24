import logging

import httpx
from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Creates the subscription to listen to blockchain events."

    def handle(self, *args, **options):
        url = settings.FIREFLY_API_URL + 'namespaces/default/subscriptions'
        logging.info(url)
        subscription_name = settings.FIREFLY_SUBSCRIPTION_NAME
        payload = {
            "transport": "websockets",
            "name": subscription_name,
            "filter": {
                "blockchainevent": {
                    "listener": ".*",
                    "name": ".*"
                },
                "events": "message_confirmed",
                "message": {
                    "author": ".*",
                    "group": ".*",
                    "tag": ".*",
                    "topics": ".*"
                },
                "transaction": {
                    "type": ".*"
                }
            },
            "options": {
                "firstEvent": "newest",
                "readAhead": 50
            }
        }

        # first check if subscription already exist and update if so else create
        res = httpx.get(url)
        subscription_exists = any([e['name'] == subscription_name for e in res.json()])
        logging.info(f'Subscription exists: {subscription_exists}')
        if subscription_exists:
            res = httpx.put(url, json=payload)
        else:
            res= httpx.post(url, json=payload)

        logging.info(res.status_code)
