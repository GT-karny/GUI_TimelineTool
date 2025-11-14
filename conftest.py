import time
from typing import Callable

import pytest


class _QtBot:
    """Minimal stand-in for pytest-qt's qtbot fixture."""

    def __init__(self) -> None:
        self._widgets = []

    def addWidget(self, widget) -> None:  # pragma: no cover - simple storage
        self._widgets.append(widget)

    def waitUntil(self, condition: Callable[[], bool], timeout: int = 1000, interval: int = 10) -> None:
        deadline = time.monotonic() + timeout / 1000.0
        while not condition():
            if time.monotonic() > deadline:
                raise AssertionError("condition not met before timeout")
            time.sleep(interval / 1000.0)


@pytest.fixture
def qtbot() -> _QtBot:
    return _QtBot()
