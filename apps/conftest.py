import pytest


@pytest.fixture(autouse=True)
def media_storage(settings, tmpdir):
    settings.MEDIA_ROOT = tmpdir.strpath


# @pytest.fixture
# def user(db) -> User:
#     return UserFactory()
