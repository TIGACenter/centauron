import json
import uuid

import pytest
from django.urls import reverse

from apps.node.models import Node
from apps.project.models import Project


@pytest.mark.django_db
def test_create_project(user, client):
    origin = Node.objects.create(identifier='test')
    data = {'name': uuid.uuid4().hex, 'origin': origin.identifier, 'identifier': uuid.uuid4().hex}
    url = reverse('api:projects-list')
    R = client.post(url, data=data)
    print(R.content)
    assert R.status_code == 201

    p = Project.objects.first()
    assert p.origin == origin
    assert p.name == data['name']
    assert p.identifier == data['identifier']

@pytest.mark.django_db
def test_create_project_data_required(user, client):
    origin = Node.objects.create(identifier='test')
    data = {}
    url = reverse('api:projects-list')
    R = client.post(url, data=data)
    print(R.content)
    assert R.status_code == 400
    data = json.loads(R.content.decode())
    assert 'name' in data
    assert 'identifier' in data
    assert 'origin' in data
