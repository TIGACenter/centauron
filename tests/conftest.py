import shutil
import uuid
from pathlib import Path

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command

from apps.core import identifier
from apps.project.models import Project
from apps.study_management.import_data.models import ImportJob
from apps.study_management.import_data.tasks import run_importer
from apps.study_management.models import Study, StudyArm
from apps.user.user_profile.models import Profile
from apps.utils import get_node_origin


@pytest.fixture
def project(user, setup):
    node = get_node_origin()
    yield Project.objects.create(created_by=user, name=str(uuid.uuid4()),
                                 identifier=identifier.create_random('project'),
                                 origin=node)


@pytest.fixture
def setup():
    call_command('setup_node')
    yield

@pytest.fixture(autouse=True)
def keycloak(settings):
    settings.KEYCLOAK_ADMIN_CONFIG = '/home/ak/Desktop/centauron_cookiecutter/centauron/keycloak.json'

@pytest.fixture
def user(client):
    username = str(uuid.uuid4())
    user = User.objects.create_user(username=username, password=username)
    profile = Profile.objects.create(user=user)
    s = client.login(username=username, password=username)
    assert s == True
    yield profile


@pytest.fixture
def study(user):
    return Study.objects.create(created_by=user, name=uuid.uuid4().hex)


@pytest.fixture
def study_arm(study):
    return StudyArm.objects.create(study=study, name=uuid.uuid4().hex)


@pytest.fixture
def study_arm_metadata_csv_path():
    return Path(__file__).parent / ('data/studyarm_metadata.csv')


@pytest.fixture
def study_arm_metadata_csv(study_arm_metadata_csv_path):
    with study_arm_metadata_csv_path.open('rb') as f:
        yield f


@pytest.fixture
def tmp_folder(settings):
    settings.TMP_DIR = Path('./tmp/')
    prepare_folder(settings.TMP_DIR)
    yield settings.TMP_DIR
    post_folder(settings.TMP_DIR)


@pytest.fixture
def import_folder(settings):
    settings.STORAGE_IMPORTER_IMPORT_DIR = Path('./import/')
    prepare_folder(settings.STORAGE_IMPORTER_IMPORT_DIR)
    yield settings.STORAGE_IMPORTER_IMPORT_DIR
    post_folder(settings.STORAGE_IMPORTER_IMPORT_DIR)


@pytest.fixture
def export_folder(settings):
    settings.STORAGE_EXPORT_DIR = Path('./export/')
    prepare_folder(settings.STORAGE_EXPORT_DIR)
    yield settings.STORAGE_EXPORT_DIR
    post_folder(settings.STORAGE_EXPORT_DIR)


def prepare_folder(fld):
    if fld.exists():
        shutil.rmtree(fld)
    fld.mkdir(parents=True)


def post_folder(fld):
    shutil.rmtree(fld)


@pytest.fixture
def test_data(setup, user, study_arm, study_arm_metadata_csv_path):
    ij = ImportJob.objects.create(created_by=user, status=ImportJob.Status.PENDING,
                                  file=str(study_arm_metadata_csv_path),
                                  study_arm=study_arm)
    run_importer(ij.id_as_str)

    # call_command('loaddata', str(Path(__file__).parent / 'data/study_management.json.gz'))
