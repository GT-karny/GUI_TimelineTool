import time
from typing import Callable

import pytest

try:  # pragma: no cover - exercised only when Qt is available
    from PySide6 import QtCore
    from PySide6.QtTest import QTest
except Exception:  # pragma: no cover - exercised in headless CI where Qt is missing
    QtCore = None  # type: ignore[assignment]
    QTest = None  # type: ignore[assignment]


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

    def wait(self, ms: int) -> None:
        """Block for the requested amount of milliseconds."""

        if ms > 0:
            time.sleep(ms / 1000.0)

    def mouseClick(self, widget, button, delay: int = 0) -> None:
        """Send a mouse click to *widget* if Qt testing helpers are available."""

        if delay:
            self.wait(delay)

        if QTest is not None and QtCore is not None:  # pragma: no branch - simple gate
            QTest.mouseClick(widget, button)
            return

        click = getattr(widget, "click", None)
        if callable(click):  # pragma: no cover - convenience fallback for stub widgets
            click()
            return

        raise RuntimeError("qtbot.mouseClick requires PySide6.QtTest when Qt is installed")


@pytest.fixture
def qtbot() -> _QtBot:
    return _QtBot()
