from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PySide6 = pytest.importorskip("PySide6", exc_type=ImportError)
pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
from PySide6 import QtCore

MainWindow = pytest.importorskip("app.ui.main_window", exc_type=ImportError).MainWindow


def test_main_window_smoke(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    qtbot.waitUntil(window.isVisible)

    assert window.plotw is not None
    assert window.inspector is not None
    assert window.telemetry_panel.isVisible()

    qtbot.mouseClick(window.toolbar.btn_play, QtCore.Qt.LeftButton)
    qtbot.wait(50)
    qtbot.mouseClick(window.toolbar.btn_stop, QtCore.Qt.LeftButton)

    window.playback.stop()
    window.close()
    qtbot.wait(20)
