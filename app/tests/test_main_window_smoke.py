from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PySide6 = pytest.importorskip("PySide6", exc_type=ImportError)
pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
from PySide6 import QtCore

MainWindowModule = pytest.importorskip("app.ui.main_window", exc_type=ImportError)
MainWindow = MainWindowModule.MainWindow
AddTrackCommand = pytest.importorskip("app.actions.undo_commands", exc_type=ImportError).AddTrackCommand


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


def test_active_track_commands_affect_selected_row(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    qtbot.waitUntil(window.isVisible)

    # add a secondary track and rebuild rows
    baseline_primary = [(k.t, k.v) for k in window.track_container.rows[0].track.keys]

    window.undo.push(AddTrackCommand(window.timeline))
    window._refresh_view()

    rows = window.track_container.rows
    assert len(rows) >= 2
    second_row = rows[1]
    second_track = second_row.track

    assert window.track_container.set_active_track(second_track.track_id) is True
    assert window.track_container.active_row is second_row
    assert window._pos_provider.track_id == second_track.track_id

    # Add key via mouse controller callback (simulates context menu add)
    assert window.mouse.add_key_cb is not None
    new_key = window.mouse.add_key_cb(1.0, 2.0)
    assert new_key is not None
    assert new_key in second_track.keys

    # Move the key via commit_drag callback to ensure track id routing
    before = (new_key.t, new_key.v)
    after = (1.5, 3.5)
    window.mouse.commit_drag(new_key, before, after)
    assert new_key.t == pytest.approx(after[0])
    assert new_key.v == pytest.approx(after[1])

    # Delete the key via delete callback
    assert window.mouse.delete_key_cb is not None
    window.mouse.delete_key_cb(new_key)
    assert new_key not in second_track.keys

    # Primary track should remain untouched
    primary_track = rows[0].track
    assert [(k.t, k.v) for k in primary_track.keys] == baseline_primary

    window.close()
    qtbot.wait(20)
