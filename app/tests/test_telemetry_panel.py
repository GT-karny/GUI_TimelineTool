from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PySide6 = pytest.importorskip("PySide6", exc_type=ImportError)
pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)

from app.telemetry.settings import TelemetrySettings
from app.ui.telemetry_panel import TelemetryPanel


@pytest.fixture
def panel(qtbot):
    widget = TelemetryPanel()
    qtbot.addWidget(widget)
    widget.show()
    return widget


def test_set_and_get_settings_roundtrip(panel):
    settings = TelemetrySettings(
        enabled=True,
        ip="192.168.10.5",
        port=12000,
        rate_hz=120,
        session_id="session-xyz",
    )

    panel.set_settings(settings)

    assert panel.get_settings() == settings


def test_placeholder_session_id_is_applied_on_set(panel):
    settings = TelemetrySettings(enabled=False, session_id=None)

    panel.set_settings(settings, session_placeholder="auto-generated")

    gathered = panel.get_settings()
    assert gathered.session_id == "auto-generated"


def test_settings_changed_signal_emits_updated_values(panel, qtbot):
    emissions: list[TelemetrySettings] = []
    panel.settings_changed.connect(emissions.append)

    panel.set_settings(TelemetrySettings())

    panel.chk_enabled.setChecked(True)
    qtbot.waitUntil(lambda: len(emissions) == 1)

    latest = emissions[-1]
    assert latest.enabled is True

    panel.txt_ip.setText("10.0.0.1")
    panel.txt_ip.editingFinished.emit()

    qtbot.waitUntil(lambda: len(emissions) == 2)
    assert emissions[-1].ip == "10.0.0.1"
