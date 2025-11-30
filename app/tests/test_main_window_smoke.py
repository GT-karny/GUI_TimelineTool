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


def test_add_keys_at_playhead_all_tracks(qtbot):
    """複数トラックがある場合、Add Keys at Playheadですべてのトラックにキーが追加されることを確認"""
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    qtbot.waitUntil(window.isVisible)
    
    # 初期状態を確認
    initial_track_count = len(window.timeline.tracks)
    assert initial_track_count >= 1
    
    # 2つ目のトラックを追加（SCALAR）
    window.undo.push(AddTrackCommand(window.timeline))
    window._refresh_view()
    qtbot.wait(50)
    
    # 3つ目のトラックを追加（VECTOR2）
    from app.core.timeline import Track, TrackType
    vector2_track = Track(track_type=TrackType.VECTOR2)
    window.undo.push(AddTrackCommand(window.timeline, track=vector2_track))
    window._refresh_view()
    qtbot.wait(50)
    
    # トラック数を確認
    assert len(window.timeline.tracks) >= 3
    
    # 各トラックのキー数を記録
    key_counts_before = {track.track_id: len(track.keys) for track in window.timeline.tracks}
    
    # プレイヘッド位置を設定
    playhead_time = 1.5
    window.plotw.playhead.setValue(playhead_time)
    qtbot.wait(50)
    
    # Add Keys at Playheadを実行
    window._on_add_key_at_playhead()
    qtbot.wait(50)
    
    # すべてのトラックにキーが追加されたことを確認
    for track in window.timeline.tracks:
        key_count_after = len(track.keys)
        key_count_before = key_counts_before[track.track_id]
        assert key_count_after == key_count_before + 1, \
            f"Track {track.track_id} ({track.name}): expected {key_count_before + 1} keys, got {key_count_after}"
        
        # 追加されたキーが正しい時刻にあることを確認
        keys_at_time = [k for k in track.keys if abs(k.t - playhead_time) < 1e-6]
        assert len(keys_at_time) == 1, \
            f"Track {track.track_id}: expected 1 key at time {playhead_time}, found {len(keys_at_time)}"
    
    # Undoが正しく動作することを確認
    window.undo.undo()
    qtbot.wait(50)
    
    for track in window.timeline.tracks:
        key_count_after_undo = len(track.keys)
        key_count_before = key_counts_before[track.track_id]
        assert key_count_after_undo == key_count_before, \
            f"Track {track.track_id}: undo failed, expected {key_count_before} keys, got {key_count_after_undo}"
    
    # Redoが正しく動作することを確認
    window.undo.redo()
    qtbot.wait(50)
    
    for track in window.timeline.tracks:
        key_count_after_redo = len(track.keys)
        key_count_before = key_counts_before[track.track_id]
        assert key_count_after_redo == key_count_before + 1, \
            f"Track {track.track_id}: redo failed, expected {key_count_before + 1} keys, got {key_count_after_redo}"
    
    window.close()
    qtbot.wait(20)