import uuid

import pytest
from django.core.management import call_command
from django.urls import reverse
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from apps.core.identifier import create_random
from apps.storage.extra_data.models import ExtraData
from apps.storage.models import File
from apps.user.user_profile.models import User
from apps.utils import get_node_origin

client = APIClient()


@pytest.fixture
def setup():
    call_command('setup_node')


@pytest.fixture
def token(annotation_backend_user):
    return Token.objects.create(user=annotation_backend_user)


@pytest.fixture
def annotation_backend_user(settings):
    username = uuid.uuid4().hex
    settings.ANNOTATION_BACKEND_USERNAME = username
    u = User.objects.create(username=username)
    u.profile.identifier = 'abc'
    u.profile.save()
    return u


@pytest.mark.django_db
def test_create_annotation_backend_user(setup, settings):
    username = uuid.uuid4().hex
    settings.ANNOTATION_BACKEND_USERNAME = username
    call_command('create_user_annotation_backend')
    qs = User.objects.filter(username=username)
    assert qs.count() == 1
    assert Token.objects.filter(user=qs.first()).count() == 1


@pytest.mark.django_db
def test_create_extra_data(setup, token):
    client.credentials(HTTP_AUTHORIZATION='Token ' + token.key)
    file = File.objects.create(name=uuid.uuid4().hex,
                               created_by=token.user.profile,
                               original_filename=uuid.uuid4().hex,
                               original_path=uuid.uuid4().hex,
                               identifier=create_random('file'))
    # data = {'event': 'annotation_created',
    #         'payload': {'task': {'extra_data': {'id': file.identifier}}},
    #         'description': uuid.uuid4().hex}
    data = {'event': 'annotation_created', 'payload': [{'id': 'c6746049-9479-4fae-848d-6ed83834b8cd',
                                                        'label': {'id': 'cee14671-92bc-4a21-bb0e-dfcaf896fdc9',
                                                                  'extra_data': {'id': '730f4cd0-136b-4380-9b28-1f589ae68031', 'code': 'NCIT_C176424', 'type': 'polygon', 'codesystem': 'NCIt'}},
                                                        'data': {'coordinates': [[[14983.905655599949, -2469.188713897651], [14983.905655599949, -2469.188713897651], [14958.314524746784, -2417.966201450996], [14907.13226304045, -2417.966201450996], [14907.13226304045, -2417.966201450996], [14676.808180405693, -2571.6337387909607], [14600.032835368067, -2674.0777866961052], [14497.6683119554, -2853.356091765316], [14446.48409777094, -2955.8011166586257], [14292.935360173811, -3135.0794217278362], [14292.935360173811, -3237.5234696329826], [14241.753098467478, -3391.1910069729474], [14190.568884283017, -3468.024287148848], [14190.568884283017, -3468.024287148848], [14164.977753429852, -3493.635054878094], [14164.977753429852, -3544.8575673247487], [14190.568884283017, -3596.0800797714037], [14292.935360173811, -3672.9133599473025], [14395.301836064606, -3800.969152569858], [14523.259442808569, -3852.191665016513], [14702.399311258861, -4005.8582253683144], [14855.948048855986, -4082.691505544215], [15086.272131490743, -4159.525762708279], [15265.413952419167, -4261.969810613426], [15418.962690016295, -4287.581555330835], [15418.962690016295, -4287.581555330835], [15521.32916590709, -4287.581555330835], [15572.511427613419, -4261.969810613426], [15649.286772651049, -4236.35904288418], [15777.244379395011, -4210.747298166771], [15828.426641101341, -4159.525762708279], [15905.20198613897, -4133.91401799087], [15981.97537869847, -4057.0807378149693], [16007.566509551634, -4031.4699700857236], [16084.341854589264, -4005.8582253683144], [16084.341854589264, -4005.8582253683144], [16161.117199626893, -3954.6357129216594], [16237.890592186392, -3852.191665016513], [16289.074806370852, -3749.746640123203], [16340.257068077186, -3672.9133599473025], [16391.43932978352, -3596.0800797714037], [16391.43932978352, -3493.635054878094], [16417.032413114815, -3391.1910069729474], [16417.032413114815, -3237.5234696329826], [16442.62354396798, -3135.0794217278362], [16442.62354396798, -3007.0236291052806], [16442.62354396798, -2955.8011166586257], [16442.62354396798, -2955.8011166586257], [16442.62354396798, -2878.967836482725], [16442.62354396798, -2878.967836482725], [14983.905655599949, -2469.188713897651]]]},
                                                        'task': {'id': 'ac525c92-e1fc-431a-8ac3-64b88340b050', 'url': 'http://localhost:8282/iipsrv.fcgi?zoomify=46dd5521-4e3a-4ccf-af34-48bf857267eb-2c1a1147-1181-4b85-b225-b7925f72f47a.ndpi', 'extra_data': {'id': file.identifier}}, 'project': 'e6e9a45f-ece6-472a-ba95-594de44172e9'}]}
    R = client.post(reverse('extra_data:create-from-annotation-backend'), data=data, format='json')
    assert R.status_code == 200
    assert R.data is None
    qs = ExtraData.objects.all()
    assert qs.count() == 1
    ed = qs.first()
    assert ed.description is None
    assert ed.data == data['payload'][0]
    assert ed.file is not None
    assert ed.created_by == token.user.profile
    assert ed.origin == get_node_origin()

    # TODO test for extra data delete


@pytest.mark.django_db
def test_create_extra_data_wrong_user(setup):
    u2 = User.objects.create(username='b')
    t = Token.objects.create(user=u2)
    client.credentials(HTTP_AUTHORIZATION='Token ' + t.key)
    data = {}
    R = client.post(reverse('extra_data:create-from-annotation-backend'), data=data, format='json')
    assert R.status_code == 403


@pytest.mark.django_db
def test_create_extra_data_400(setup, token):
    client.credentials(HTTP_AUTHORIZATION='Token ' + token.key)

    data = {'event': 'annotation_created',
            'payload': {'task': {'extra_data': {'id': 'abc'}}},
            'description': uuid.uuid4().hex}
    R = client.post(reverse('extra_data:create-from-annotation-backend'), data=data, format='json')
    assert R.status_code == 400

    data = {'event': 'annotation_created',
            'payload': {'task': {'extra_data': {}}},
            'description': uuid.uuid4().hex}
    R = client.post(reverse('extra_data:create-from-annotation-backend'), data=data, format='json')
    assert R.status_code == 400
