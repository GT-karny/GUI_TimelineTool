# ui/parameter_study_window.py
"""パラメータスタディモードウィンドウ - トラックのパラメータをリアルタイムに操作してUDP送信する。"""
from __future__ import annotations

import logging
from typing import Callable, Dict, Optional
from PySide6 import QtWidgets, QtCore, QtGui
import pyqtgraph as pg

from ..core.timeline import Timeline, Track, TrackType
from ..playback.telemetry_bridge import TelemetryBridge
from ..services.telemetry_sender import TrackTelemetrySnapshot, snapshots_to_payload

logger = logging.getLogger(__name__)


class FloatTrackSlider(QtWidgets.QWidget):
    """FloatTrack用の範囲設定可能なスライダーコントロール。"""

    value_changed = QtCore.Signal(float)

    def __init__(self, track: Track, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self._track = track
        self._value: float = 0.0
        self._min_value: float = -1.0
        self._max_value: float = 1.0
        self._updating = False

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # トラック名
        name_label = QtWidgets.QLabel(track.name)
        name_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(name_label)

        # 範囲設定コントロール
        range_layout = QtWidgets.QHBoxLayout()
        range_layout.addWidget(QtWidgets.QLabel("Min:"))
        self.min_spin = QtWidgets.QDoubleSpinBox()
        self.min_spin.setRange(-1e9, 1e9)
        self.min_spin.setDecimals(6)
        self.min_spin.setValue(self._min_value)
        self.min_spin.valueChanged.connect(self._on_min_changed)
        range_layout.addWidget(self.min_spin)

        range_layout.addWidget(QtWidgets.QLabel("Max:"))
        self.max_spin = QtWidgets.QDoubleSpinBox()
        self.max_spin.setRange(-1e9, 1e9)
        self.max_spin.setDecimals(6)
        self.max_spin.setValue(self._max_value)
        self.max_spin.valueChanged.connect(self._on_max_changed)
        range_layout.addWidget(self.max_spin)

        layout.addLayout(range_layout)

        # スライダーと値表示
        slider_layout = QtWidgets.QHBoxLayout()
        self.slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.slider.setMinimum(0)
        self.slider.setMaximum(10000)
        self.slider.setValue(5000)  # 中央値
        self.slider.valueChanged.connect(self._on_slider_changed)
        slider_layout.addWidget(self.slider)

        self.value_label = QtWidgets.QLabel("0.000000")
        self.value_label.setMinimumWidth(100)
        self.value_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        slider_layout.addWidget(self.value_label)

        layout.addLayout(slider_layout)

        # 初期値を設定
        self._update_slider_from_value()

    def _on_min_changed(self, value: float) -> None:
        """最小値が変更されたときの処理。"""
        if value >= self._max_value:
            self._updating = True
            self.min_spin.setValue(self._max_value - 0.01)
            self._updating = False
            return
        self._min_value = float(value)
        self._update_slider_from_value()

    def _on_max_changed(self, value: float) -> None:
        """最大値が変更されたときの処理。"""
        if value <= self._min_value:
            self._updating = True
            self.max_spin.setValue(self._min_value + 0.01)
            self._updating = False
            return
        self._max_value = float(value)
        self._update_slider_from_value()

    def _on_slider_changed(self, value: int) -> None:
        """スライダーが変更されたときの処理。"""
        if self._updating:
            return
        # スライダー値を実際の値に変換
        ratio = value / 10000.0
        self._value = self._min_value + (self._max_value - self._min_value) * ratio
        self.value_label.setText(f"{self._value:.6f}")
        self.value_changed.emit(self._value)

    def _update_slider_from_value(self) -> None:
        """現在の値からスライダー位置を更新。"""
        if self._max_value == self._min_value:
            return
        ratio = (self._value - self._min_value) / (self._max_value - self._min_value)
        ratio = max(0.0, min(1.0, ratio))
        slider_value = int(ratio * 10000)
        self._updating = True
        self.slider.setValue(slider_value)
        self._updating = False

    def get_value(self) -> float:
        """現在の値を取得。"""
        return self._value

    def set_value(self, value: float) -> None:
        """値を設定。"""
        self._value = float(value)
        self._update_slider_from_value()
        self.value_label.setText(f"{self._value:.6f}")

    def get_range(self) -> tuple[float, float]:
        """値域を取得。"""
        return (self._min_value, self._max_value)

    def set_range(self, min_value: float, max_value: float) -> None:
        """値域を設定。"""
        self._min_value = float(min_value)
        self._max_value = float(max_value)
        self.min_spin.setValue(self._min_value)
        self.max_spin.setValue(self._max_value)
        self._update_slider_from_value()


class Vector2TrackPlot(QtWidgets.QWidget):
    """Vector2Track用の2Dプロットコントロール。"""

    value_changed = QtCore.Signal(float, float)  # vx, vy

    def __init__(self, track: Track, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self._track = track
        self._vx: float = 0.0
        self._vy: float = 0.0
        self._updating = False
        self._dragging = False

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # トラック名
        name_label = QtWidgets.QLabel(track.name)
        name_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(name_label)

        # プロット
        self.plot = pg.PlotWidget(background="#2b2b2b")
        self.plot.showGrid(x=True, y=True, alpha=0.3)
        label_x = track.label_x if track.label_x is not None else "X"
        label_y = track.label_y if track.label_y is not None else "Y"
        self.plot.setLabel("bottom", label_x)
        self.plot.setLabel("left", label_y)
        self.plot.setAspectLocked(False)
        self.plot.setXRange(-1.0, 1.0)
        self.plot.setYRange(-1.0, 1.0)

        # ドラッグ可能なポイント
        self.draggable_point = pg.ScatterPlotItem(
            [self._vx],
            [self._vy],
            size=12,
            brush=pg.mkBrush(40, 120, 255, 180),
            pen=pg.mkPen(0, 60, 160, 200),
        )
        self.plot.addItem(self.draggable_point)

        layout.addWidget(self.plot)

        # 値表示
        value_layout = QtWidgets.QHBoxLayout()
        value_layout.addWidget(QtWidgets.QLabel(f"{label_x}:"))
        self.x_label = QtWidgets.QLabel("0.000000")
        self.x_label.setMinimumWidth(100)
        value_layout.addWidget(self.x_label)

        value_layout.addWidget(QtWidgets.QLabel(f"{label_y}:"))
        self.y_label = QtWidgets.QLabel("0.000000")
        self.y_label.setMinimumWidth(100)
        value_layout.addWidget(self.y_label)

        value_layout.addStretch()
        layout.addLayout(value_layout)

        # ドラッグ処理
        self.plot.scene().installEventFilter(self)

    def eventFilter(self, obj, event) -> bool:
        """マウスイベントをフィルタリングしてドラッグ処理。"""
        if obj is not self.plot.scene():
            return super().eventFilter(obj, event)

        from PySide6.QtCore import QEvent

        if event.type() == QEvent.GraphicsSceneMousePress:
            if event.button() == QtCore.Qt.LeftButton:
                view_pos = self.plot.plotItem.vb.mapSceneToView(event.scenePos())
                self._dragging = True
                self._update_position(view_pos.x(), view_pos.y())
                return True

        elif event.type() == QEvent.GraphicsSceneMouseMove:
            if self._dragging:
                view_pos = self.plot.plotItem.vb.mapSceneToView(event.scenePos())
                self._update_position(view_pos.x(), view_pos.y())
                return True

        elif event.type() == QEvent.GraphicsSceneMouseRelease:
            if event.button() == QtCore.Qt.LeftButton and self._dragging:
                self._dragging = False
                return True

        return super().eventFilter(obj, event)

    def _update_position(self, x: float, y: float) -> None:
        """位置を更新。"""
        self._updating = True
        try:
            self._vx = float(x)
            self._vy = float(y)
            self.draggable_point.setData([self._vx], [self._vy])
            self.x_label.setText(f"{self._vx:.6f}")
            self.y_label.setText(f"{self._vy:.6f}")
            self.value_changed.emit(self._vx, self._vy)
        finally:
            self._updating = False

    def get_value(self) -> tuple[float, float]:
        """現在の値を取得。"""
        return (self._vx, self._vy)

    def set_value(self, vx: float, vy: float) -> None:
        """値を設定。"""
        if not self._updating:
            self._updating = True
            try:
                self._vx = float(vx)
                self._vy = float(vy)
                self.draggable_point.setData([self._vx], [self._vy])
                self.x_label.setText(f"{self._vx:.6f}")
                self.y_label.setText(f"{self._vy:.6f}")
                self.value_changed.emit(self._vx, self._vy)
            finally:
                self._updating = False

    def get_range(self) -> tuple[tuple[float, float], tuple[float, float]]:
        """値域を取得。((x_min, x_max), (y_min, y_max))"""
        x_range = self.plot.plotItem.vb.viewRange()[0]
        y_range = self.plot.plotItem.vb.viewRange()[1]
        return ((x_range[0], x_range[1]), (y_range[0], y_range[1]))

    def set_range(self, x_range: tuple[float, float], y_range: tuple[float, float]) -> None:
        """値域を設定。"""
        self.plot.setXRange(x_range[0], x_range[1])
        self.plot.setYRange(y_range[0], y_range[1])


class ParameterStudyWindow(QtWidgets.QMainWindow):
    """パラメータスタディモードウィンドウ。"""

    def __init__(
        self,
        timeline: Timeline,
        telemetry_bridge: TelemetryBridge,
        parent: Optional[QtWidgets.QWidget] = None,
        *,
        playhead_getter: Optional[Callable[[], float]] = None,
        undo_stack: Optional[QtGui.QUndoStack] = None,
    ) -> None:
        super().__init__(parent)
        self._timeline = timeline
        self._telemetry_bridge = telemetry_bridge
        self._playhead_getter = playhead_getter
        self._undo_stack = undo_stack
        self._track_controls: Dict[str, QtWidgets.QWidget] = {}
        self._track_values: Dict[str, tuple[float, ...]] = {}
        self._send_mode: str = "immediate"  # "immediate" or "rate"
        self._send_rate_hz: int = 90
        self._frame_index: int = 0
        self._rate_timer: Optional[QtCore.QTimer] = None

        self.setWindowTitle("Parameter Study Mode")
        self.resize(800, 600)

        self._init_ui()
        self._build_track_controls()

    def _init_ui(self) -> None:
        """UIを初期化。"""
        central = QtWidgets.QWidget(self)
        layout = QtWidgets.QVBoxLayout(central)
        layout.setContentsMargins(8, 8, 8, 8)

        # 送信モード切り替え
        mode_layout = QtWidgets.QHBoxLayout()
        mode_layout.addWidget(QtWidgets.QLabel("Send Mode:"))

        self.send_mode_group = QtWidgets.QButtonGroup(self)
        self.immediate_radio = QtWidgets.QRadioButton("Immediate")
        self.immediate_radio.setChecked(True)
        self.immediate_radio.toggled.connect(
            lambda checked: self._on_send_mode_changed("immediate" if checked else None)
        )
        self.send_mode_group.addButton(self.immediate_radio, 0)

        self.rate_radio = QtWidgets.QRadioButton("Rate")
        self.rate_radio.toggled.connect(
            lambda checked: self._on_send_mode_changed("rate" if checked else None)
        )
        self.send_mode_group.addButton(self.rate_radio, 1)

        mode_layout.addWidget(self.immediate_radio)
        mode_layout.addWidget(self.rate_radio)

        mode_layout.addWidget(QtWidgets.QLabel("Rate (Hz):"))
        self.rate_spin = QtWidgets.QSpinBox()
        self.rate_spin.setRange(1, 240)
        self.rate_spin.setValue(self._send_rate_hz)
        self.rate_spin.valueChanged.connect(self._on_rate_changed)
        mode_layout.addWidget(self.rate_spin)

        mode_layout.addStretch()
        layout.addLayout(mode_layout)

        # キー追加ボタン
        if self._playhead_getter is not None and self._undo_stack is not None:
            button_layout = QtWidgets.QHBoxLayout()
            self.add_keys_btn = QtWidgets.QPushButton("Add Keys at Playhead")
            self.add_keys_btn.clicked.connect(self._on_add_keys_at_playhead)
            button_layout.addWidget(self.add_keys_btn)
            button_layout.addStretch()
            layout.addLayout(button_layout)

        # スクロール可能なトラックコントロール
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.tracks_widget = QtWidgets.QWidget()
        self.tracks_layout = QtWidgets.QVBoxLayout(self.tracks_widget)
        self.tracks_layout.setContentsMargins(0, 0, 0, 0)
        self.tracks_layout.addStretch()

        scroll.setWidget(self.tracks_widget)
        layout.addWidget(scroll)

        self.setCentralWidget(central)

    def _build_track_controls(self) -> None:
        """トラックコントロールを構築。"""
        # 既存のコントロールをクリア
        for control in self._track_controls.values():
            self.tracks_layout.removeWidget(control)
            control.deleteLater()
        self._track_controls.clear()
        self._track_values.clear()

        # 各トラックのコントロールを作成
        for track in self._timeline.iter_tracks():
            if track.track_type == TrackType.SCALAR:
                control = FloatTrackSlider(track, self)
                control.value_changed.connect(
                    lambda v, t=track: self._on_track_value_changed(t.track_id, (v,))
                )
                self._track_controls[track.track_id] = control
                self._track_values[track.track_id] = (0.0,)
            elif track.track_type == TrackType.VECTOR2:
                control = Vector2TrackPlot(track, self)
                control.value_changed.connect(
                    lambda vx, vy, t=track: self._on_track_value_changed(t.track_id, (vx, vy))
                )
                self._track_controls[track.track_id] = control
                self._track_values[track.track_id] = (0.0, 0.0)

            # レイアウトに追加（最後のstretchの前に）
            count = self.tracks_layout.count()
            self.tracks_layout.insertWidget(count - 1, control)

    def _on_track_value_changed(self, track_id: str, values: tuple[float, ...]) -> None:
        """トラックの値が変更されたときの処理。"""
        self._track_values[track_id] = values
        if self._send_mode == "immediate":
            self._send_telemetry(force_send=True)

    def _on_send_mode_changed(self, mode: Optional[str]) -> None:
        """送信モードが変更されたときの処理。"""
        if mode is None:
            return
        if mode == "immediate":
            self._send_mode = "immediate"
            if self._rate_timer is not None:
                self._rate_timer.stop()
                self._rate_timer = None
        elif mode == "rate":
            self._send_mode = "rate"
            if self._rate_timer is None:
                self._rate_timer = QtCore.QTimer(self)
                self._rate_timer.timeout.connect(self._on_rate_timer)
            period_ms = int(1000 / self._send_rate_hz)
            self._rate_timer.start(period_ms)
            self._frame_index = 0

    def _on_rate_changed(self, hz: int) -> None:
        """送信レートが変更されたときの処理。"""
        self._send_rate_hz = int(hz)
        if self._send_mode == "rate" and self._rate_timer is not None:
            period_ms = int(1000 / self._send_rate_hz)
            self._rate_timer.setInterval(period_ms)

    def _on_rate_timer(self) -> None:
        """一定レート送信タイマーのコールバック。"""
        self._send_telemetry(force_send=True)
        self._frame_index += 1

    def _send_telemetry(self, force_send: bool = False) -> None:
        """テレメトリを送信。"""
        # 現在のトラック値からスナップショットを構築
        track_snapshots = []
        for track in self._timeline.iter_tracks():
            values = self._track_values.get(track.track_id, (0.0,))
            snapshot = TrackTelemetrySnapshot(name=track.name, values=values)
            track_snapshots.append(snapshot)

        payload = snapshots_to_payload(track_snapshots)

        # TelemetryBridgeに送信
        # 即座送信モードではforce_send=Trueで即座に送信
        # 一定レート送信モードではQTimerで定期的にforce_send=Trueで送信
        self._telemetry_bridge.update_snapshot(
            playing=False,
            playhead_ms=0,
            frame_index=self._frame_index,
            track_snapshots=payload,
            force_send=force_send,
        )

    def get_ranges(self) -> Dict[str, dict]:
        """全トラックの値域を取得。"""
        ranges = {}
        for track_id, control in self._track_controls.items():
            if isinstance(control, FloatTrackSlider):
                min_val, max_val = control.get_range()
                ranges[track_id] = {"min": min_val, "max": max_val}
            elif isinstance(control, Vector2TrackPlot):
                x_range, y_range = control.get_range()
                ranges[track_id] = {
                    "x_range": [x_range[0], x_range[1]],
                    "y_range": [y_range[0], y_range[1]],
                }
        return ranges

    def set_ranges(self, ranges: Dict[str, dict]) -> None:
        """全トラックの値域を設定。"""
        for track_id, range_data in ranges.items():
            control = self._track_controls.get(track_id)
            if control is None:
                continue
            if isinstance(control, FloatTrackSlider):
                if "min" in range_data and "max" in range_data:
                    control.set_range(range_data["min"], range_data["max"])
            elif isinstance(control, Vector2TrackPlot):
                if "x_range" in range_data and "y_range" in range_data:
                    x_range = tuple(range_data["x_range"])
                    y_range = tuple(range_data["y_range"])
                    control.set_range(x_range, y_range)

    def get_current_values(self) -> Dict[str, tuple[float, ...]]:
        """全トラックの現在値を取得。"""
        return dict(self._track_values)

    def _on_add_keys_at_playhead(self) -> None:
        """再生カーソル位置に現在のパラメータスタディ値をキーとして追加。"""
        if self._playhead_getter is None or self._undo_stack is None:
            return

        t = self._playhead_getter()
        if t < 0.0:
            t = 0.0

        from PySide6.QtGui import QUndoCommand
        from ..actions.undo_commands import AddKeyCommand

        # 複数のキーを一度に追加するための親コマンド
        root_cmd = QUndoCommand("Add Keys from Parameter Study")
        
        for track in self._timeline.iter_tracks():
            values = self._track_values.get(track.track_id, (0.0,))
            if track.track_type == TrackType.SCALAR:
                v = values[0] if len(values) > 0 else 0.0
                cmd = AddKeyCommand(
                    self._timeline,
                    track.track_id,
                    t,
                    v,
                    label=f"Add Key: {track.name}",
                    parent=root_cmd,
                )
            elif track.track_type == TrackType.VECTOR2:
                vx = values[0] if len(values) > 0 else 0.0
                vy = values[1] if len(values) > 1 else 0.0
                cmd = AddKeyCommand(
                    self._timeline,
                    track.track_id,
                    t,
                    0.0,  # vは0.0（Vector2Trackでは使用しない）
                    vx=vx,
                    vy=vy,
                    label=f"Add Key: {track.name}",
                    parent=root_cmd,
                )

        if root_cmd.childCount() > 0:
            self._undo_stack.push(root_cmd)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        """ウィンドウが閉じられるときの処理。"""
        if self._rate_timer is not None:
            self._rate_timer.stop()
        # 送信を停止
        self._telemetry_bridge.update_snapshot(
            playing=False,
            playhead_ms=0,
            frame_index=0,
            track_snapshots=[],
            force_send=False,
        )
        super().closeEvent(event)

