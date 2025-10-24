import csv
import uuid
from unittest.mock import patch

import pytest
from django.urls import reverse

from apps.storage.models import File
from apps.storage.storage_importer.models import ImportFolder
from apps.study_management.import_data.models import ImportJob
from apps.study_management.import_data.tasks import run_importer
from apps.study_management.tasks import export_arm_files_to_csv, export_imported_files_to_csv
from apps.utils import get_node_origin


@pytest.mark.django_db
def test_import_metadata_csv(user, client, study, study_arm, study_arm_metadata_csv, tmp_folder):
    url = reverse('study_management:import_data:form', kwargs=dict(pk=study.pk, arm_pk=study_arm.pk))
    filename = f'{uuid.uuid4()}.csv'
    R = client.post(url, {'file': study_arm_metadata_csv})
    print(R.content)
    assert R.status_code == 302
    assert ImportJob.objects.count() == 1
    ij = ImportJob.objects.first()
    assert ij.created_by == user
    assert ij.status == ImportJob.Status.PENDING
    assert len(list(tmp_folder.iterdir())) == 1


@pytest.mark.django_db
def test_import_metadata_celery_task(user, setup, client, study, study_arm, tmp_folder, study_arm_metadata_csv_path):
    ij = ImportJob.objects.create(created_by=user, status=ImportJob.Status.PENDING,
                                  file=str(study_arm_metadata_csv_path),
                                  study_arm=study_arm)
    run_importer(ij.id_as_str)

    ij = ImportJob.objects.get(pk=ij.pk)
    assert ij.status == ImportJob.Status.SUCCESS
    assert ImportFolder.objects.count() == 1
    i_f = ImportFolder.objects.first()
    assert i_f.study == study
    assert study_arm.files.count() == 1
    f = study_arm.files.first()
    assert f.name == '9c9dc546-8452-42e6-8d50-9aa9dbae4b5d.tiff'
    assert f.origin == get_node_origin()
    assert f.case.origin == get_node_origin()
    assert not f.imported
    assert study.codes.count() == 1
    code = study.codes.first()
    assert code.code == 'HE'
    assert code.codesystem is not None
    assert code.origin == get_node_origin()
    assert code.study_codes.first() == study
    assert code.created_by == user
    assert code.codesystem.origin == get_node_origin()
    assert code.codesystem_name == code.codesystem.name
    assert f.case.name == 'A2020-000600'


@pytest.mark.django_db
def test_export_files_as_csv_view(user, setup, client, study, study_arm, tmp_folder, study_arm_metadata_csv_path):
    url = reverse('study_management:arm-export', kwargs=dict(pk=study.pk, arm_pk=study_arm.pk))
    with patch('apps.study_management.tasks.export_arm_files_to_csv.delay'):
        R = client.post(url)
        assert R.status_code == 302


@pytest.mark.django_db
def test_export_files_as_csv_task(user, settings, setup, client, study, study_arm, tmp_folder,
                                  study_arm_metadata_csv_path, export_folder, test_data):
    dst = f'{uuid.uuid4()}.csv'
    export_arm_files_to_csv(study_arm.id_as_str, dst)

    export_file = export_folder / dst
    assert export_file.exists()
    assert not export_file.name.endswith('.exporting')

    with export_file.open() as f:
        reader = csv.DictReader(f, fieldnames=['id', 'identifier', 'case', 'name', 'path', 'original_path',
                                               'original_filename', 'origin'])
        next(reader)  # skip header
        line = next(reader)
        file = study_arm.files.first()
        assert line['identifier'] == file.identifier
        assert line['origin'] == file.origin.identifier
        assert line['id'] == file.id_as_str
        assert line['case'] == file.case.name
        assert line['name'] == file.name
        assert line['path'] == ''  # not imported
        assert line['original_path'] == file.original_path
        assert line['original_filename'] == file.original_filename


@pytest.mark.django_db
def test_export_only_imported_files_view(user, settings, setup, client, study, study_arm, tmp_folder, export_folder,
                                         test_data):
    url = reverse('study_management:arm-export-csv', kwargs=dict(pk=study.pk, arm_pk=study_arm.pk))
    with patch('apps.study_management.tasks.export_imported_files_to_csv.delay'):
        R = client.post(url)
    assert R.status_code == 302


@pytest.mark.django_db
def test_export_only_imported_files_task(user, settings, setup, client, study, study_arm, tmp_folder, export_folder,
                                         test_data):
    dst = uuid.uuid4().hex
    # export but no imported files yet. expect no files in exported csv file.
    export_imported_files_to_csv(study_arm.id_as_str, dst)
    f = settings.STORAGE_EXPORT_DIR / dst
    assert f.exists()
    with f.open() as fp:
        l = fp.readlines()
        assert len(l) == 1
        assert l[0] == 'identifier\n'

    # now with imported files.
    File.objects.update(imported=True)
    export_imported_files_to_csv(study_arm.id_as_str, dst)
    f = settings.STORAGE_EXPORT_DIR / dst
    assert f.exists()
    with f.open() as fp:
        l = fp.readlines()
        print(l)
        assert len(l) == 2
        assert l[0] == 'identifier\n'
        assert l[1] == study_arm.files.first().identifier + '\n'
