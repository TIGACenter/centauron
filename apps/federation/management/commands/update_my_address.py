from django.conf import settings
from django.core.management.base import BaseCommand

from apps.dsf.client import update, get, send_bundle
from apps.dsf.tasks import create_bundle
from apps.node.models import Node


class Command(BaseCommand):
    help = "Sends request to the Centauron Certificate Authority to refresh the certificate fingerprints."

    def handle(self, *args, **options):
        qs = Node.objects.all()

        process = "http://centauron.net/bpe/Process/message-send|1.0"
        input = [{'valueBoolean': True, "type": {"coding": [{"system": "http://centauron.net/fhir/CodeSystem/centauron", "code": "dsf"}]}}]


        import json
        eps = {
            'type': 'endpoint-update',
            'data': [{
                'organization': 'fhir.ak.dev.centauron.net',
                'address': 'http://abd.com/',
            }]
        }

        bundle = create_bundle(process=process,
                               message_name="sendMessage",
                               profile="http://centauron.net/fhir/StructureDefinition/message/task-send|1.0",
                               target_organization_identifier='fhir.ak.dev.centauron.net',
                               input=input,
                               message=json.dumps(eps))
        # task['input'].append({
        #     "valueString": f'{constants.IDENTIFIER_ORGANIZATION}|{target_organization_identifier}',  # "inviteUser",
        #     "type": {
        #         "coding": [
        #             {
        #                 "system": constants.CODESSYTEM_CENTAURON,
        #                 "code": "recipient"
        #             }
        #         ]
        #     }
        # })
        import json
        print(json.dumps(bundle))
        send_bundle(bundle)

        return
        # {"process": "http://centauron.net/bpe/Process/message-send|1.0", "profile": "http://centauron.net/fhir/StructureDefinition/message/task-send|1.0", "resource": "task", "message_name": "sendMessage"}

        for node in qs:

            # search for my endpoint
            url = f'{node.address_fhir_server}/Endpoint/?identifier={settings.IDENTIFIER}'
            try:
                endpoint = get(url)
                r = endpoint.json()
                if r['total'] != 1:
                    self.stderr.write(f'Endpoint resource not found at {node.address_fhir_server}')
                    continue
                endpoint = r['entry'][0]['resource']

                print(endpoint)
                endpoint['address'] = settings.FHIR_SERVER

                url = f'{node.address_fhir_server}/Endpoint/{endpoint["id"]}'
                response = update(url, endpoint)
                print(response)

                self.stdout.write(f"Update the fhir server address at {node.address_fhir_server}")

            except Exception as e:
                self.stderr.write(f'Error updating address at {node.address_fhir_server}: {e}')
