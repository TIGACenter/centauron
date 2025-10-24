import io
import uuid
from unittest.mock import patch

import pytest
from django.urls import reverse

from apps.project.import_data.tasks import import_csv
from apps.storage.models import File


@pytest.mark.django_db
def test_import_csv_view(user, client, project, test_data, setup):
    url = reverse('project:import_data:csv', kwargs=dict(pk=project.pk))

    with io.StringIO() as buffer:
        buffer.writelines(['identifier', File.objects.first().identifier])
        buffer.seek(0)
        with patch('apps.project.import_data.tasks.import_csv.delay'):
            R = client.post(url, {'file': buffer})
            assert R.status_code == 302


@pytest.mark.django_db
def test_import_csv_task(user, client, project, test_data, setup, tmp_folder):
    tmp_file = tmp_folder / uuid.uuid4().hex
    with tmp_file.open('w') as buffer:
        buffer.writelines(['identifier\n', File.objects.first().identifier])
    import_csv(str(tmp_file), project.id_as_str)

    assert project.files.count() == 1
