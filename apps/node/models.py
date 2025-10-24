import logging

from django.conf import settings
from django.db import models

from apps.core.managers import BaseManager
from apps.core.models import IdentifieableMixin, Base, CreatedByMixin
from apps.federation.messages import UserMessage, Message


class NodeManager(BaseManager):

    def get_me(self):
        return self.get(identifier=settings.IDENTIFIER)

    def all_but_me(self):
        return self.exclude(identifier=settings.IDENTIFIER)


class Node(IdentifieableMixin, CreatedByMixin, Base):
    objects = NodeManager()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['identifier'], name='unique_identifier_per_nodes')
        ]

    human_readable = models.CharField(max_length=100)
    address_fhir_server = models.CharField(max_length=250, null=True, default=None,
                                           blank=True)  # the address of the FHIR server.
    address_centauron = models.CharField(
        max_length=250)  # the address of the CENTAURON server (necessary for file transfer).
    cdn_address = models.CharField(max_length=250)  # the address of the CENTAURON server (necessary for file transfer).
    did = models.CharField(max_length=100, unique=True)
    common_name = models.CharField(max_length=200)
    api_address = models.CharField(max_length=250, null=True, default=None, blank=True)

    def __str__(self):
        return self.human_readable

    @staticmethod
    def import_node(current_user: 'Profile', message: UserMessage, **kwargs):

        if isinstance(message, Message):
            message = message.object
            data = message.content

        if isinstance(message, dict):
            message = message['object']
            data = message['content']

        # if current_user is None:
        #     current_user = get_user_node()

        if isinstance(data, dict):
            identifier = data['identifier']
            name = data['node_name']
            data_common_name = data['common_name']
            data_cdn_address = data['cdn_address']
            data_address = data['address']
            data_did = data['did']
            data_api = data['api_address']
        else:
            identifier = data.identifier
            name = data.node_name
            data_common_name = data.common_name
            data_cdn_address = data.cdn_address
            data_address = data.address
            data_did = data.did
            data_api = data.api_address

        qs = Node.objects.filter(identifier=identifier)

        if not qs.exists():
            Node.create_from_node_data(data)
        else:
            logging.info('Updating node %s', identifier)
            # update node
            node = qs.first()
            node.human_readable = name
            node.common_name = data_common_name
            node.address_centauron = data_address
            node.cdn_address = data_cdn_address
            node.api_address = data_api
            # node.did = data_did
            node.save()

    @staticmethod
    def create_from_node_data(data):
        from apps.user.user_profile.models import Profile

        identifier = data['identifier']
        did = data['did']
        node = Node.objects.create(
            human_readable=data.get('node_name', ''),
            # address_fhir_server=data['address_fhir_server'],
            address_centauron=data['address'],
            common_name=data['common_name'],
            identifier=identifier,
            cdn_address=data['cdn_address'],
            did=did,
            api_address=data['api_address'],
        )
        # create the profile for the node
        Profile.objects.create(
            identifier=identifier,
            identity=did,
            node=node,
            human_readable=identifier
        )

        return node

    def delete_node(self):
        pass
