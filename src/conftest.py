import pytest
from pytest_django import Settings


@pytest.fixture(autouse=True)
def _disable_linear(settings: Settings) -> None:
    settings.LINEAR = None
