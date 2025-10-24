import csv
import time
import uuid
from pathlib import Path

import pytest
from django.contrib.auth.models import User

from apps.core import identifier
from apps.project.project_case.models import Case
from apps.storage.models import File
from apps.storage.storage_importer.models import ImportFolder
from apps.study_management.import_data.importer import MetadataImporter, TileSetHandler
from apps.study_management.models import Study, StudyArm
from apps.study_management.tile_management.models import TileSet
from apps.user.user_profile.models import Profile


# class TestMetadataImporter(TestCase):
@pytest.mark.django_db
def test_metadata_importer_update_rows():
    # create a sample csv in io buffer
    file = f'/tmp/{uuid.uuid4()}'
    with open(file, 'w') as f:
        writer = csv.DictWriter(f, fieldnames=['identifier'])
        writer.writeheader()
        n = 1000
        fs = []
        # cs = []
        for i in range(n):
            id = identifier.create_random('file')
            # case = str(uuid.uuid4())
            fs.append(File(identifier=id))
            # cs.append(Case(name=case))
            writer.writerow(dict(identifier=id))
        File.objects.bulk_create(fs)
        # Case.objects.bulk_create(cs)
    created_by = Profile()
    import_folder = ImportFolder()
    MetadataImporter(created_by, import_folder).run(Path(file))


@pytest.mark.django_db
def test_metadata_importer_insert():
    # create a sample csv in io buffer
    file = f'/tmp/{uuid.uuid4()}'
    user = User.objects.create(username='abcabc')
    profile = Profile.objects.create(user=user)
    with open(file, 'w') as f:
        writer = csv.DictWriter(f, fieldnames=['name', 'content_type', 'codes', 'size', 'case', 'path', 'src'])
        writer.writeheader()
        n = 10_000
        fs = []
        cs = []
        for i in range(n):
            if i <= n / 8:
                case = Case(name=str(uuid.uuid4()), created_by=profile)
                cs.append(case)
                src = File(identifier=identifier.create_random('file'), created_by=profile)
                fs.append(src)
                src = src.identifier
                case = case.name
            else:
                src = None
                case = None
            writer.writerow(dict(name=str(uuid.uuid4()),
                                 path=str(uuid.uuid4()),
                                 src=src,
                                 content_type='image/png',
                                 codes='abc#def,foo#bar',
                                 size=1111,
                                 case=case))
        File.objects.bulk_create(fs)
        Case.objects.bulk_create(cs)
    import_folder = ImportFolder.objects.create(path=str(uuid.uuid4()))
    s = Study.objects.create(name=str(uuid.uuid4()))
    sa = StudyArm.objects.create(name=str(uuid.uuid4()), study=s)
    ts = TileSet.objects.create(name=str(uuid.uuid4()), study_arm=sa)
    handler = TileSetHandler(ts)
    t0 = time.perf_counter()
    MetadataImporter(profile, import_folder, handlers=[handler]).run(Path(file))
    t1 = time.perf_counter()
    print(f'Import took {t1 - t0}sec')


@pytest.mark.django_db
def test_metadata_importer_insert_and_update():
    # create a sample csv in io buffer
    file = f'/tmp/{uuid.uuid4()}'
    user = User.objects.create(username='abcabc')
    profile = Profile.objects.create(user=user)
    with open(file, 'w') as f:
        writer = csv.DictWriter(f, fieldnames=['name', 'identifier', 'content_type', 'codes', 'size', 'case', 'path',
                                               'src'])
        writer.writeheader()
        n = 100_000
        fs = []
        cs = []
        for i in range(n):
            case = Case(name=str(uuid.uuid4()), created_by=profile)
            src = File(identifier=identifier.create_random('file'), created_by=profile)
            name = str(uuid.uuid4())
            f = File(name=name,
                     created_by=profile,
                     original_filename=name,
                     content_type=str(uuid.uuid4()),
                     size=1111,
                     case=case,
                     original_path=str(uuid.uuid4()),
                     originating_from=src)
            if i >= n / 2:
                f.identifier = identifier.create_random('file')

            fs.append(f)
            fs.append(src)
            cs.append(case)
            writer.writerow(dict(name=f.name, path=f.path, src=src.identifier,
                                 content_type=f.content_type,
                                 codes='abc#def,foo#bar',
                                 identifier=f.identifier,
                                 size=f.size,
                                 case=case))
        File.objects.bulk_create(fs)
        Case.objects.bulk_create(cs)
    import_folder = ImportFolder.objects.create(path=str(uuid.uuid4()))
    t0 = time.perf_counter()
    MetadataImporter(profile, import_folder).run(Path(file))
    t1 = time.perf_counter()
    print(f'Import took {t1 - t0}sec')
    assert File.objects.count() == 2 * n + (n / 2)
    assert Case.objects.count() == n


@pytest.mark.django_db
def test_metadata_importer_import_identifiers():
    # create a sample csv in io buffer
    file = f'/tmp/{uuid.uuid4()}'
    user = User.objects.create(username='abcabc')
    profile = Profile.objects.create(user=user)
    with open(file, 'w') as f:
        writer = csv.DictWriter(f, fieldnames=['identifier'])
        writer.writeheader()
        n = 10_000
        fs = []
        cs = []
        for i in range(n):
            case = Case(name=str(uuid.uuid4()), created_by=profile)
            src = File(identifier=identifier.create_random('file'), created_by=profile)
            name = str(uuid.uuid4())
            f = File(name=name,
                     created_by=profile,
                     original_filename=name,
                     content_type=str(uuid.uuid4()),
                     size=1111,
                     case=case,
                     original_path=str(uuid.uuid4()),
                     originating_from=src)
            f.identifier = identifier.create_random('file')

            fs.append(f)
            fs.append(src)
            cs.append(case)
            writer.writerow(dict(identifier=f.identifier))

        File.objects.bulk_create(fs)
        Case.objects.bulk_create(cs)
    import_folder = ImportFolder.objects.create(path=str(uuid.uuid4()))
    s = Study.objects.create(name=str(uuid.uuid4()))
    sa = StudyArm.objects.create(name=str(uuid.uuid4()), study=s)
    ts = TileSet.objects.create(name=str(uuid.uuid4()), study_arm=sa)
    handler = TileSetHandler(ts)
    t0 = time.perf_counter()
    MetadataImporter(profile, import_folder, handlers=[handler]).run(Path(file))
    t1 = time.perf_counter()
    print(f'Import took {t1 - t0}sec')
    # assert File.objects.count() == 2 * n + (n / 2)
    # assert Case.objects.count() == n
