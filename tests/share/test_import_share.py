import json
import uuid
from pathlib import Path

import pytest
from django.core.management import call_command
from django.db.models import Q

from apps.core import identifier
from apps.federation.inbox.models import InboxMessage
from apps.federation.inbox.tasks import process_inbox_message
from apps.federation.messages import Message, ShareObject
from apps.project.models import Project
from apps.project.project_case.models import Case
from apps.share.api import ShareBuilder, CodesHandler
from apps.share.models import Share
from apps.storage.extra_data.models import ExtraData
from apps.storage.models import File
from apps.terminology.models import CodeSystem, Code
from apps.utils import get_node_origin
from tests import test_utils


@pytest.mark.django_db
def test_import_share():
    call_command('setup_node')

    created_by = 'user1'
    recipient = 'user2'
    created_by_user = test_utils.create_user(created_by)
    recipient_user = test_utils.create_user(recipient)
    origin = get_node_origin()
    project = Project.objects.create(created_by=recipient_user.profile,
                                     identifier=identifier.create_random('project'))
    n_files = 5
    n_cases = 5
    n_concepts = 2
    n_extra_data = 3

    concept_1 = 'concept_1'
    concept_2 = 'concept_2'
    cs = CodeSystem.objects.create(name='abc', uri='abc')
    concept_1 = Code.objects.create(code=concept_1, codesystem=cs, origin=origin, created_by=created_by_user.profile)
    concept_2 = Code.objects.create(code=concept_2, codesystem=cs, origin=origin, created_by=created_by_user.profile)
    concepts = Code.objects.all()

    for _ in range(n_cases):
        case = Case.objects.create(name=str(uuid.uuid4()),
                                   created_by=created_by_user.profile,
                                   origin=origin,
                                   identifier=identifier.create_random('case'))
        for _ in range(n_files):
            f = File.objects.create(case=case, identifier=identifier.create_random('file'), name=str(uuid.uuid4()),
                                    created_by=created_by_user.profile,
                                    origin=origin,
                                    content_type='image/png', size=11111,
                                    original_filename=str(uuid.uuid4()),
                                    original_path=str(uuid.uuid4()))
            f.codes.set(concepts)

            for _ in range(n_extra_data):
                ExtraData.objects.create(file=f, data={'test': 123}, application_identifier='abcabc')

    total_extra_data = ExtraData.objects.count()

    qs = File.objects.all()
    case_ids = qs.values_list('case_id', flat=True).distinct()
    share_builder = ShareBuilder(name=str(uuid.uuid4()), created_by=created_by_user.profile)
    share_builder.add_file_handler(data=qs)
    share_builder.add_case_handler(data=case_ids)
    file_concepts = qs.values_list('id', 'codes', named=True)
    share_builder.add_codes_handler(data=file_concepts, handler_init_kwargs={'__name__': CodesHandler.name_files})
    share_builder.add_extra_data_handler(data=ExtraData.objects.all())
    # share_builder.add_permission_handler(data=','.join(list(map(lambda e: f'\'{e}\'', file_identifiers))))
    share = share_builder.build(project.identifier)

    # delete all cases
    # delete all files
    case_identifiers = Case.objects.values_list('identifier', flat=True)
    file_identifiers = File.objects.values_list('identifier', flat=True)
    Case.objects.filter().delete()
    File.objects.filter().delete()
    Code.objects.filter().delete()
    ExtraData.objects.filter().delete()

    message = Message(from_=created_by, to=recipient, hash='',
                      object=ShareObject(content=share.content))

    # import share
    Share.import_share(message=message)
    project = Project.objects.get(pk=project.pk)

    remote_share = Share.objects.filter(~Q(pk=share.pk)).first()
    assert remote_share is not None
    total_files = n_cases * n_files
    assert remote_share.cases.count() == n_cases
    assert remote_share.files.count() == total_files

    for c_i in case_identifiers:
        assert Case.objects.get_by_identifier(c_i) is not None

    for c_i in file_identifiers:
        assert File.objects.get_by_identifier(c_i) is not None

    assert project.cases.count() == n_cases
    assert project.files.count() == total_files
    assert Case.objects.count() == n_cases
    assert File.objects.count() == total_files
    assert ExtraData.objects.count() == total_extra_data

    for case in Case.objects.all():
        assert case.files.count() == n_files

    assert Code.objects.count() == n_concepts
    assert project.codeset.codes.count() == n_concepts

    for file in project.files.all():
        assert file.codes.count() == 2
        assert file.extra_data.count() == n_extra_data


@pytest.mark.django_db
def test_import_share_from_inbox_message(setup, project, user):
    node = get_node_origin()
    data = Path(__file__).parent / ('data/import_share_message.json')
    d = json.load(data.open())
    im = InboxMessage.objects.create(message=d, recipient=node, sender=node)
    project.identifier = 'fhir.ak.dev.centauron.net#project::e0bf0cd5-6ae7-4009-9ed2-25dc46fdb77a'
    project.save()

    process_inbox_message(im.id_as_str)

    im = InboxMessage.objects.get(pk=im.pk)

    assert im.processed
    assert not im.processing

    assert project.files.count() == 2548
    assert project.cases.count() == 1000
