import uuid

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command

from apps.node.models import Node
from apps.user.user_profile.models import Profile

User = get_user_model()


@pytest.mark.django_db
def test_setup_node(settings):
    settings.FHIR_SERVER = 'http://test.com/fhir'
    settings.IDENTIFIER = uuid.uuid4().hex
    settings.NODE_NAME = uuid.uuid4().hex

    call_command('setup_node')

    assert Node.objects.count() == 1
    assert Node.objects.filter(identifier=settings.IDENTIFIER).count() == 1
    node = Node.objects.first()
    assert node.human_readable == settings.NODE_NAME
    assert node.address_fhir_server == settings.FHIR_SERVER
    assert node.identifier == settings.IDENTIFIER

    assert User.objects.count() == 1
    assert User.objects.filter(username='node').count() == 1
    assert Profile.objects.count() == 1
    assert Profile.objects.filter(user__username='node').count() == 1
