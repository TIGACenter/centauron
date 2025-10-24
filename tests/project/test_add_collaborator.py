import json
import uuid

import pytest
from django.urls import reverse

from apps.federation.inbox.models import InboxMessage
from apps.federation.messages import Message, ProjectObject, ProjectMessageContent, DataViewMessageContent, \
    CreateMessage
from apps.federation.outbox.models import OutboxMessage
from apps.node.models import Node
from apps.project.models import ProjectMembership, Project, DataView


@pytest.mark.django_db
def test_add_collaborator(setup, user, client, project, settings, respx_mock):
    url = reverse('project:collaborator-add', kwargs=dict(pk=project.pk))
    n2 = Node.objects.create(identifier=f'{uuid.uuid4()}.test.com')

    R = client.post(url, {'node': n2.id_as_str})
    assert R.status_code == 302

    assert project.members.get(node=n2).status == ProjectMembership.Status.INVITED
    assert OutboxMessage.objects.count() == 1
    om = OutboxMessage.objects.first()
    print(om)
    msg = om.message
    msg = json.loads(msg)
    print(msg)
    assert msg['type'] == 'create'
    assert msg['to'] == n2.identifier
    assert msg['from'] == settings.IDENTIFIER
    assert not om.processed
    assert not om.processing

    # TODO assert extra data and rest of message


@pytest.mark.django_db
@pytest.mark.skip()
def test_accept_invite_node_not_found(setup, user, client, project, settings, respx_mock):
    url = reverse('project:invite-action')
    with pytest.raises(Node.DoesNotExist):
        R = client.post(url, {'url': uuid.uuid4().hex, 'project': uuid.uuid4().hex, 'accept': True})


@pytest.mark.django_db
def test_accept_invite(setup, user, client, project, settings, respx_mock):
    url = reverse('project:invite-action')
    n2 = Node.objects.create(identifier=f'{uuid.uuid4()}.test.com')
    p = project.to_message_object().json()  # {'identifier': uuid.uuid4().hex, 'id': uuid.uuid4().hex, 'name': uuid.uuid4().hex}
    # p = json.dumps(p)
    # no url
    R = client.post(url, {'node': n2.id_as_str, 'accept': True, 'project': p})
    assert R.status_code == 400

    R = client.post(url, {'node': n2.id_as_str, 'url': uuid.uuid4().hex, 'accept': True, 'project': p})
    assert R.status_code == 302

    assert OutboxMessage.objects.count() == 1
    m = OutboxMessage.objects.first()
    assert m.recipient == n2
    print(m.message)
    d = json.loads(m.message)

    assert d['type'] == 'update'
    assert d['from'] == settings.IDENTIFIER
    assert d['to'] == n2.identifier
    o = d['object']
    assert o['type'] == 'project-invitation'
    assert o['content']['accept']
    assert o['content']['project_identifier'] == project.identifier


@pytest.mark.django_db
def test_import_project(setup, project, user, ):
    project_identifier = f"fhir.ak.dev.centauron.net#project::{uuid.uuid4()}"
    n2 = Node.objects.create(identifier=uuid.uuid4().hex)
    name = uuid.uuid4().hex
    description = uuid.uuid4().hex
    dv_name = uuid.uuid4().hex
    dv_query = {'id': uuid.uuid4().hex}
    dv_datatable_config = {'id': uuid.uuid4().hex}
    dv_model = DataView.Model.CASE

    msg = CreateMessage(
        from_=uuid.uuid4().hex,
        to=uuid.uuid4().hex,
        object=ProjectObject(
        content=[
            ProjectMessageContent(
                id=uuid.uuid4().hex,
                identifier=project_identifier,
                name=name,
                description=description,
                origin=n2.identifier
            ),
            DataViewMessageContent(
                name=dv_name,
                model=dv_model,
                query=dv_query,
                datatable_config=dv_datatable_config
            )
        ]
    ))

    msg = msg.dict()
    msg = Message(**msg)

    # msg = "{\"type\":\"create\",\"object\":{\"type\":\"project\",\"content\":" \
    #       "[{\"type\":\"project\",\"id\":\"ee623b2a-71dd-4bf8-9d86-2ebcf1c393d3\"," \
    #       "\"identifier\":\"" + project_identifier + "\",\"name\":\"" + name + "\"," \
    #                                                                            "\"description\":\"" + description + "\",\"origin\":\"" + n2.identifier + "\"}]},\"from\":\"fhir.ak.dev.centauron.net\",\"to\":\"fhir.ak.dev.centauron.net\",\"hash\":\"\"}"
    # msg = json.loads(msg)
    # msg = Message(**msg)

    kw = {'message': msg, 'inbox_message': InboxMessage()}
    Project.import_project(**kw)

    qs = Project.objects.filter_by_identifier(project_identifier)
    assert qs.count() == 1
    p: Project = qs.first()
    assert p.name == name
    assert p.origin == n2
    assert p.description == description

    dv = p.views.first()
    assert dv is not None
    assert dv.name == dv_name
    assert dv.query == dv_query
    assert dv.model == dv_model
    assert dv.datatable_config == dv_datatable_config



@pytest.mark.django_db
def test_remove_member_from_project(setup, client, project):
    n2 = Node.objects.create()
    pm = ProjectMembership.objects.create(project=project, node=n2)

    assert project.members.count() == 1

    url = reverse('project:collaborator-delete', kwargs=dict(pk=project.pk))
    R = client.post(url, {'member': pm.id_as_str})
    assert R.status_code == 302
    assert project.members.count() == 0
