"""パラメータスタディウィンドウのテスト。"""
from __future__ import annotations

import pytest
from PySide6 import QtWidgets, QtCore
from PySide6.QtCore import QSettings

from ..core.timeline import Timeline, Track, TrackType, Keyframe
from ..playback.telemetry_bridge import TelemetryBridge
from ..ui.parameter_study_window import (
    ParameterStudyWindow,
    FloatTrackSlider,
    Vector2TrackPlot,
)


@pytest.fixture
def qapp():
    """Qtアプリケーションを作成。"""
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


@pytest.fixture
def timeline():
    """テスト用のタイムラインを作成。"""
    tl = Timeline()
    # ScalarTrackを追加
    scalar_track = Track(name="ScalarTrack", track_type=TrackType.SCALAR)
    scalar_track.keys = [
        Keyframe(0.0, 0.0),
        Keyframe(5.0, 1.0),
    ]
    tl.tracks.append(scalar_track)
    
    # Vector2Trackを追加
    vector2_track = Track(name="Vector2Track", track_type=TrackType.VECTOR2)
    vector2_track.keys = [
        Keyframe(0.0, 0.0, vx=0.0, vy=0.0),
        Keyframe(5.0, 0.0, vx=1.0, vy=1.0),
    ]
    tl.tracks.append(vector2_track)
    
    return tl


@pytest.fixture
def telemetry_bridge():
    """テスト用のTelemetryBridgeを作成。"""
    settings = QSettings("TestApp", "TestApp")
    return TelemetryBridge(settings)


def test_float_track_slider_creation(qapp, timeline):
    """FloatTrackSliderが正常に作成されることを確認。"""
    track = timeline.tracks[0]
    assert track.track_type == TrackType.SCALAR
    
    slider = FloatTrackSlider(track)
    assert slider is not None
    assert slider._track == track


def test_vector2_track_plot_creation(qapp, timeline):
    """Vector2TrackPlotが正常に作成されることを確認。"""
    # Vector2Trackを探す
    vector2_track = None
    for track in timeline.tracks:
        if track.track_type == TrackType.VECTOR2:
            vector2_track = track
            break
    
    assert vector2_track is not None, "Vector2Trackが見つかりません"
    assert vector2_track.track_type == TrackType.VECTOR2
    
    plot = Vector2TrackPlot(vector2_track)
    assert plot is not None
    assert plot._track == vector2_track


def test_parameter_study_window_creation(qapp, timeline, telemetry_bridge):
    """ParameterStudyWindowが正常に作成されることを確認。"""
    window = ParameterStudyWindow(timeline, telemetry_bridge)
    assert window is not None
    assert window._timeline == timeline
    assert window._telemetry_bridge == telemetry_bridge


def test_parameter_study_window_tracks(qapp, timeline, telemetry_bridge):
    """ParameterStudyWindowが全トラックを表示することを確認。"""
    window = ParameterStudyWindow(timeline, telemetry_bridge)
    
    # トラックコントロールが作成されていることを確認（少なくとも2つ以上）
    assert len(window._track_controls) >= 2
    
    # ScalarTrackのコントロールが存在することを確認
    scalar_track = None
    for track in timeline.tracks:
        if track.track_type == TrackType.SCALAR:
            scalar_track = track
            break
    
    assert scalar_track is not None, "ScalarTrackが見つかりません"
    assert scalar_track.track_id in window._track_controls
    assert isinstance(window._track_controls[scalar_track.track_id], FloatTrackSlider)
    
    # Vector2Trackのコントロールが存在することを確認
    vector2_track = None
    for track in timeline.tracks:
        if track.track_type == TrackType.VECTOR2:
            vector2_track = track
            break
    
    assert vector2_track is not None, "Vector2Trackが見つかりません"
    assert vector2_track.track_id in window._track_controls
    assert isinstance(window._track_controls[vector2_track.track_id], Vector2TrackPlot)


def test_float_track_slider_value_change(qapp, timeline):
    """FloatTrackSliderの値変更が正常に動作することを確認。"""
    track = timeline.tracks[0]
    slider = FloatTrackSlider(track)
    
    # 値変更シグナルを確認
    received_values = []
    
    def on_value_changed(value: float):
        received_values.append(value)
    
    slider.value_changed.connect(on_value_changed)
    
    # スライダーを変更
    slider.slider.setValue(7500)  # 75%の位置
    qapp.processEvents()
    
    # 値が変更されていることを確認
    assert len(received_values) > 0
    assert slider.get_value() != 0.0


def test_vector2_track_plot_value_change(qapp, timeline):
    """Vector2TrackPlotの値変更が正常に動作することを確認。"""
    # Vector2Trackを探す
    vector2_track = None
    for track in timeline.tracks:
        if track.track_type == TrackType.VECTOR2:
            vector2_track = track
            break
    
    assert vector2_track is not None, "Vector2Trackが見つかりません"
    plot = Vector2TrackPlot(vector2_track)
    
    # 値変更シグナルを確認
    received_values = []
    
    def on_value_changed(vx: float, vy: float):
        received_values.append((vx, vy))
    
    plot.value_changed.connect(on_value_changed)
    
    # 値を設定
    plot.set_value(0.5, 0.5)
    qapp.processEvents()
    
    # 値が変更されていることを確認
    assert len(received_values) > 0, "シグナルが発火していません"
    vx, vy = plot.get_value()
    assert vx == 0.5
    assert vy == 0.5


def test_send_mode_switching(qapp, timeline, telemetry_bridge):
    """送信モードの切り替えが正常に動作することを確認。"""
    window = ParameterStudyWindow(timeline, telemetry_bridge)
    
    # 初期状態は即座送信モード
    assert window._send_mode == "immediate"
    assert window.immediate_radio.isChecked()
    
    # 一定レート送信モードに切り替え
    window.rate_radio.setChecked(True)
    qapp.processEvents()
    
    assert window._send_mode == "rate"
    assert window.rate_radio.isChecked()
    assert window._rate_timer is not None
    assert window._rate_timer.isActive()
    
    # 即座送信モードに戻す
    window.immediate_radio.setChecked(True)
    qapp.processEvents()
    
    assert window._send_mode == "immediate"
    assert window.immediate_radio.isChecked()
    # タイマーが停止していることを確認
    if window._rate_timer is not None:
        assert not window._rate_timer.isActive()

