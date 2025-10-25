# ui/timeline_plot.py
from __future__ import annotations
from typing import Optional, Iterable, Set
from PySide6 import QtWidgets
import pyqtgraph as pg
import numpy as np

from ..core.timeline import Timeline, Keyframe
from ..core.interpolation import evaluate


class TimelinePlot(QtWidgets.QWidget):
    """
    タイムラインの描画専任コンポーネント。
    - 曲線・キー点・プレイヘッド表示
    - X/Yレンジの明示制御（自動レンジは無効）
    - UIイベントや編集ロジックは持たない（別モジュールに委譲）
    """

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)

        # モデル参照（外部から set_timeline で注入）
        self.timeline: Optional[Timeline] = None

        # ---- Plot 構築 ----
        self.plot = pg.PlotWidget(background="w")
        self.plot.showGrid(x=True, y=True, alpha=0.25)
        self.plot.setLabel("bottom", "Time (s)")
        self.plot.setLabel("left", "Value")

        # AutoRange は完全停止（勝手に動かさない）
        self.plot.plotItem.vb.enableAutoRange(x=False, y=False)

        # 曲線・点・プレイヘッド
        self.curve_item = self.plot.plot([], [], pen=pg.mkPen(0, 0, 0, 220, width=2))
        self.points = pg.ScatterPlotItem(size=10)
        self.plot.addItem(self.points)

        self.playhead = pg.InfiniteLine(
            pos=0.0, angle=90, movable=False, pen=pg.mkPen(200, 0, 0, 200)
        )
        self.plot.addItem(self.playhead)

        # レイアウト
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.plot)

    # ---- 基本API ----
    def set_timeline(self, tl: Timeline) -> None:
        """使用する Timeline を注入し、初回描画を行う。"""
        self.timeline = tl
        self.update_curve()
        # 初期レンジは呼び出し側で fit_x/y を行うことを想定

    def set_playhead(self, t: float) -> None:
        """プレイヘッド位置を秒で設定。"""
        self.playhead.setValue(float(max(0.0, t)))

    def update_curve(self) -> None:
        """曲線（補間結果）を再描画。"""
        if self.timeline is None:
            self.curve_item.setData([], [])
            return

        ks = self.timeline.track.sorted()
        tmax = max(self.timeline.duration_s, max((k.t for k in ks), default=0.0))
        dense_t = np.linspace(0.0, max(1e-3, tmax), 1200)
        dense_v = evaluate(self.timeline.track, dense_t)
        self.curve_item.setData(dense_t, dense_v)

    def update_points(self, keys: Iterable[Keyframe], selected_ids: Set[int]) -> None:
        """キー点を再描画。選択点は強調表示。"""
        spots = []
        for k in keys:
            is_sel = (id(k) in selected_ids)
            spots.append(
                {
                    "pos": (k.t, k.v),
                    "data": id(k),  # unique id（ヒットテスト側が使うなら参照）
                    "brush": pg.mkBrush(255, 160, 0, 220) if is_sel else pg.mkBrush(40, 120, 255, 180),
                    "size": 12 if is_sel else 10,
                    "pen": pg.mkPen(180, 100, 0, 220) if is_sel else pg.mkPen(0, 60, 160, 200),
                }
            )
        self.points.setData(spots)

    # ---- レンジ制御 ----
    def fit_x(self, padding: float = 0.02) -> None:
        """Xレンジを[0, max(1.0, tmax)]に設定。"""
        if self.timeline is None:
            self.viewbox.setXRange(0.0, 1.0, padding=padding)
            return
        ks = self.timeline.track.sorted()
        tmax = max(self.timeline.duration_s, max((k.t for k in ks), default=0.0))
        self.viewbox.setXRange(0.0, max(1.0, tmax), padding=padding)

    def fit_y(self, padding: float = 0.05) -> None:
        """キー点に基づいてYレンジを設定（ゼロ幅/非有限は安全側に調整）。"""
        if self.timeline is None:
            self.viewbox.setYRange(-1.0, 1.0, padding=0)
            return

        ks = self.timeline.track.sorted()
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
