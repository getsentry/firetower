from typing import Any

import pytest


@pytest.fixture(autouse=True)
def _disable_linear(settings: Any) -> None:
    settings.LINEAR = None
