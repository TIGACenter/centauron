import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_import_invalid_code(user, client, project):
    url = reverse('project:import_data:node', kwargs=dict(pk=project.pk))
    R = client.post(url, data={'code': 'abc'})

    assert len(R.context_data['form'].errors) == 1
    assert 'code' in R.context_data['form'].errors
    assert R.context_data['form'].errors['code'][0] == 'Code is invalid.'


@pytest.mark.django_db
def test_import_valid_code(user, client, project):
    url = reverse('project:import_data:node', kwargs=dict(pk=project.pk))
    R = client.post(url, data={'code': 'abc'})

    assert len(R.context_data['form'].errors) == 1
    assert 'code' in R.context_data['form'].errors
    assert R.context_data['form'].errors['code'][0] == 'Code is invalid.'

