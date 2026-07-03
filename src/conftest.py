import pytest
from pytest_django.fixtures import SettingsWrapper


@pytest.fixture(autouse=True)
def _disable_linear(settings: SettingsWrapper) -> None:
    settings.LINEAR = None
