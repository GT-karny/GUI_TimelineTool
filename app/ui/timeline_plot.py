# ui/timeline_plot.py
from __future__ import annotations
from typing import Optional, Set
from PySide6 import QtWidgets
import pyqtgraph as pg
import numpy as np

from ..core.timeline import Track, Keyframe, InterpMode
from ..core.interpolation import evaluate
from ..playback.controller import PlaybackController
from ..interaction.selection import SelectedKey


class TimelinePlot(QtWidgets.QWidget):
    """
    タイムラインの描画専任コンポーネント。
    - 曲線・キー点・プレイヘッド表示
    - X/Yレンジの明示制御（自動レンジは無効）
    - UIイベントや編集ロジックは持たない（別モジュールに委譲）
    """

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)

        # モデル参照（外部から set_track で注入）
        self._track: Optional[Track] = None
        self._duration_s: float = 10.0
        self._playback: Optional[PlaybackController] = None

        # ---- Plot 構築 ----
        self.plot = pg.PlotWidget(background="#2b2b2b")
        self.plot.showGrid(x=True, y=True, alpha=0.3)
        self.plot.setLabel("bottom", "Time (s)")
        self.plot.setLabel("left", "Value")

        # AutoRange は完全停止（勝手に動かさない）
        self.plot.plotItem.vb.enableAutoRange(x=False, y=False)

        # 曲線・点・プレイヘッド
        self.curve_item = self.plot.plot([], [], pen=pg.mkPen(200, 200, 200, 255, width=2))
        self.handle_lines = pg.PlotDataItem(
            [],
            [],
            pen=pg.mkPen(150, 150, 150, 150, width=1),
        )
        self.plot.addItem(self.handle_lines)
        self.handle_points = pg.ScatterPlotItem(size=8)
        self.handle_points.setZValue(2)
        self.plot.addItem(self.handle_points)
        self.points = pg.ScatterPlotItem(size=10)
        self.points.setZValue(1)
        self.plot.addItem(self.points)

        self.playhead = pg.InfiniteLine(
            pos=0.0, angle=90, movable=False, pen=pg.mkPen(255, 50, 50, 200)
        )
        self.plot.addItem(self.playhead)

        # レイアウト
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.plot)

    # ---- 基本API ----
    def set_track(self, track: Optional[Track]) -> None:
        """描画対象の Track を注入し、初期描画を行う。"""
        self._track = track
        self.update_curve()
        self.update_points()

    def set_duration(self, duration_s: float) -> None:
        """トラックの時間範囲を設定する。"""
        self._duration_s = max(0.001, float(duration_s))

    def set_playback_controller(self, playback: Optional[PlaybackController]) -> None:
        """プレイバック制御と連動させる。None で切断。"""
        if self._playback is playback:
            return

        if self._playback is not None:
            self._playback.remove_playhead_listener(self._on_playback_playhead)

        self._playback = playback

        if playback is not None:
            playback.add_playhead_listener(self._on_playback_playhead)

    def set_playhead(self, t: float) -> None:
        """プレイヘッド位置を秒で設定。"""
        self.playhead.setValue(float(max(0.0, t)))

    def update_curve(self) -> None:
        """曲線（補間結果）を再描画。"""
        if self._track is None:
            self.curve_item.setData([], [])
            return

        ks = self._track.sorted()
        tmax = max(self._duration_s, max((k.t for k in ks), default=0.0))
        dense_t = np.linspace(0.0, max(1e-3, tmax), 1200)
        dense_v = evaluate(self._track, dense_t)
        self.curve_item.setData(dense_t, dense_v)

    def update_points(self, selected: Set[SelectedKey] | None = None) -> None:
        """キー点およびハンドルを再描画。選択点は強調表示。"""

        if selected is None:
            selected = set()

        if self._track is None:
            self.points.setData([])
            self.handle_points.setData([])
            self.handle_lines.setData([], [])
            return

        keys = self._track.sorted()
        selected_key_ids = {sel.item_id for sel in selected if sel.component == "key"}
        selected_handle_ids = {
            sel.item_id
            for sel in selected
            if sel.component != "key" and sel.item_id is not None
        }

        key_spots = []
        for k in keys:
            key_id = id(k)
            is_sel = key_id in selected_key_ids
            key_spots.append(
                {
                    "pos": (k.t, k.v),
                    "data": key_id,
                    "brush": pg.mkBrush(255, 160, 0, 220)
                    if is_sel
                    else pg.mkBrush(40, 120, 255, 180),
                    "size": 12 if is_sel else 10,
                    "pen": pg.mkPen(180, 100, 0, 220)
                    if is_sel
                    else pg.mkPen(0, 60, 160, 200),
                }
            )
        self.points.setData(key_spots)

        if getattr(self._track, "interp", None) == InterpMode.BEZIER:
            handle_spots = []
            line_x: list[float] = []
            line_y: list[float] = []
            for k in keys:
                key_id = id(k)
                for component, handle in (
                    ("handle_in", getattr(k, "handle_in", None)),
                    ("handle_out", getattr(k, "handle_out", None)),
                ):
                    if handle is None:
                        continue
                    handle_id = id(handle)
                    is_handle_sel = handle_id in selected_handle_ids
                    handle_spots.append(
                        {
                            "pos": (handle.t, handle.v),
                            "data": (component, key_id, handle_id),
                            "brush": pg.mkBrush(255, 200, 80, 220)
                            if is_handle_sel
                            else pg.mkBrush(90, 90, 90, 200),
                            "size": 11 if is_handle_sel else 8,
                            "pen": pg.mkPen(200, 140, 40, 220)
                            if is_handle_sel
                            else pg.mkPen(70, 70, 70, 200),
                        }
                    )
                    line_x.extend([k.t, handle.t, float("nan")])
                    line_y.extend([k.v, handle.v, float("nan")])
            self.handle_points.setData(handle_spots)
            if line_x and line_y:
                self.handle_lines.setData(line_x, line_y)
            else:
                self.handle_lines.setData([], [])
        else:
            self.handle_points.setData([])
            self.handle_lines.setData([], [])

    # ---- レンジ制御 ----
    def fit_x(self, padding: float = 0.02) -> None:
        """Xレンジを[0, max(1.0, tmax)]に設定。"""
        if self._track is None:
            self.viewbox.setXRange(0.0, 1.0, padding=padding)
            return
        ks = self._track.sorted()
        tmax = max(self._duration_s, max((k.t for k in ks), default=0.0))
        self.viewbox.setXRange(0.0, max(1.0, tmax), padding=padding)

    def fit_y(self, padding: float = 0.05) -> None:
        """キー点に基づいてYレンジを設定（ゼロ幅/非有限は安全側に調整）。"""
        if self._track is None:
            self.viewbox.setYRange(-1.0, 1.0, padding=0)
            return

        ks = self._track.sorted()
        if ks:
            vmin = min(k.v for k in ks)
            vmax = max(k.v for k in ks)
        else:
            vmin, vmax = -1.0, 1.0

        # 非有限/極小レンジの保護
        if not np.isfinite(vmin) or not np.isfinite(vmax) or abs(vmax - vmin) < 1e-6:
            c = 0.5 * (vmin + vmax)
            vmin, vmax = c - 1.0, c + 1.0

        pad = padding * (vmax - vmin)
        self.viewbox.setYRange(vmin - pad, vmax + pad, padding=0)

    # ---- 参照ヘルパ ----
    @property
    def viewbox(self) -> pg.ViewBox:
        return self.plot.plotItem.vb

    # ---- 内部コールバック ----
    def _on_playback_playhead(self, playhead_s: float, _playing: bool) -> None:
        self.set_playhead(playhead_s)
