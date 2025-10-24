import pytest

from apps.core import identifier
from apps.project.project_ground_truth.models import GroundTruthSchema


@pytest.mark.django_db
def test_import_ground_truth_schema(project):

    gt = GroundTruthSchema.objects.create(
        project=project,
        identifier=identifier.create_random('ground-truth-schema')
    )
