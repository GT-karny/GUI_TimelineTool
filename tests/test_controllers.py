from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import importlib
import os
import sys

_existing_modules = set(sys.modules)
_previous_env = os.environ.get("TIMELINE_TOOL_USE_QT_STUBS")
_using_stubs = False

try:
    importlib.import_module("PySide6.QtWidgets")
except Exception:
    _using_stubs = True
    os.environ["TIMELINE_TOOL_USE_QT_STUBS"] = "1"
    sitecustomize = importlib.import_module("sitecustomize")
    importlib.reload(sitecustomize)
finally:
    if _previous_env is None:
        os.environ.pop("TIMELINE_TOOL_USE_QT_STUBS", None)
    else:
        os.environ["TIMELINE_TOOL_USE_QT_STUBS"] = _previous_env

_stub_modules = (
    {name for name in sys.modules if name not in _existing_modules and name.startswith("PySide6")}
    if _using_stubs
    else set()
)


import pytest


@pytest.fixture(scope="module", autouse=True)
def _cleanup_qt_stubs():
    try:
        yield
    finally:
        for name in _stub_modules:
            sys.modules.pop(name, None)

from app.core.timeline import Timeline
from app.ui.controllers import ProjectController, TelemetryController


class WindowStub:
    def __init__(self) -> None:
        self.timeline = Timeline()
        self.sample_rate_hz = 90.0
        self._base_title = "Timeline"

        plot = MagicMock()
        timeline_plot = MagicMock()
        timeline_plot.plot = plot
        self._active_row = MagicMock()
        self._active_row.timeline_plot = timeline_plot
        self._active_row.track = self.timeline.track

        self.track_container = MagicMock()
        self.track_container.active_row = self._active_row
        self.track_container.primary_row = self._active_row
        self.track_container.rows = []
        self.track_container.update_duration = MagicMock()

        def _set_timeline(new_timeline: Timeline) -> None:
            self._active_row.track = new_timeline.track

        self.track_container.set_timeline.side_effect = _set_timeline

        self.playback = MagicMock()
        self._pos_provider = MagicMock()
        self.mouse = SimpleNamespace(timeline=self.timeline)
        self.sel = SimpleNamespace(clear=MagicMock())
        self.undo = MagicMock()
        self.toolbar = MagicMock()
        self.plotw = MagicMock()
        self._on_track_rows_changed = MagicMock()
        self._refresh_view = MagicMock()

        self._status_bar = MagicMock()
        self._actions = []
        self.setWindowTitle = MagicMock()

    def statusBar(self):  # noqa: D401 - mimic Qt API
        """Return the stubbed status bar."""
        return self._status_bar

    def addAction(self, action) -> None:  # noqa: D401 - mimic Qt API
        """Capture actions added to the window."""
        self._actions.append(action)

    def _current_track(self):  # noqa: D401 - mimic MainWindow helper
        """Return the first track of the current timeline."""
        return self.timeline.track


def test_project_controller_apply_project_updates_window_state():
    window = WindowStub()
    controller = ProjectController(window)

    new_timeline = Timeline(duration_s=20.0)
    path = Path("project.json")

    controller.apply_project(new_timeline, sample_rate=120.0, path=path)

    assert window.timeline is new_timeline
    assert window.sample_rate_hz == 120.0
    window.track_container.set_timeline.assert_called_with(new_timeline)
    window.track_container.update_duration.assert_called_with(new_timeline.duration_s)
    window._on_track_rows_changed.assert_called_once()
    window.playback.set_timeline.assert_called_with(new_timeline)
    window._pos_provider.set_binding.assert_called_once()
    assert window.mouse.timeline is new_timeline
    window.sel.clear.assert_called_once()
    window.undo.clear.assert_called_once()
    window.undo.setClean.assert_called_once()
    window.toolbar.set_duration.assert_called_with(new_timeline.duration_s)
    window.toolbar.set_interp.assert_called_with(new_timeline.track.interp.value)
    window.toolbar.set_rate.assert_called_with(120.0)
    window.playback.set_playhead.assert_called_with(0.0)
    window.plotw.fit_x.assert_called_once()
    window.plotw.fit_y.assert_called_once_with(0.15)
    window._refresh_view.assert_called_once()
    assert controller.current_project_path == path
    window.setWindowTitle.assert_called_with(f"{window._base_title} - {path.name}")


def test_telemetry_controller_publishes_snapshots_and_tracks_frames():
    timeline = Timeline()
    playback = MagicMock()
    playback.playhead = 1.5

    telemetry_bridge = MagicMock()
    telemetry_bridge.settings = MagicMock()
    telemetry_bridge.assembler.session_id = "session-xyz"

    telemetry_panel = MagicMock()

    snapshot_builder = MagicMock(side_effect=[f"snap-{i}" for i in range(5)])
    payload_builder = MagicMock(side_effect=[{"frame": i} for i in range(5)])

    controller = TelemetryController(
        playback=playback,
        telemetry_bridge=telemetry_bridge,
        telemetry_panel=telemetry_panel,
        timeline_getter=lambda: timeline,
        snapshot_builder=snapshot_builder,
        payload_builder=payload_builder,
    )

    controller.on_playback_playhead_changed(0.25, playing=True)
    telemetry_bridge.update_snapshot.assert_called_with(
        playing=True,
        playhead_ms=250,
        frame_index=0,
        track_snapshots={"frame": 0},
    )

    controller.on_playback_playhead_changed(0.5, playing=True)
    telemetry_bridge.update_snapshot.assert_called_with(
        playing=True,
        playhead_ms=500,
        frame_index=1,
        track_snapshots={"frame": 1},
    )

    controller.on_playback_playhead_changed(0.75, playing=False)
    telemetry_bridge.update_snapshot.assert_called_with(
        playing=False,
        playhead_ms=750,
        frame_index=2,
        track_snapshots={"frame": 2},
    )

    playback.playhead = 1.2
    controller.on_playback_state_changed(True)
    telemetry_bridge.update_snapshot.assert_called_with(
        playing=True,
        playhead_ms=1200,
        frame_index=0,
        track_snapshots={"frame": 3},
    )
    assert snapshot_builder.call_count == 4
    assert payload_builder.call_count == 4
