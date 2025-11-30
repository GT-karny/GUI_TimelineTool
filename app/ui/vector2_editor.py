# ui/vector2_editor.py
"""2Dプロット編集ウィンドウ - Vector2TrackのキーをX-Y平面で編集する。"""
from __future__ import annotations
from typing import Optional, Callable
from PySide6 import QtWidgets, QtCore
import pyqtgraph as pg
import numpy as np

from ..core.timeline import Track, Keyframe, TrackType


class Vector2EditorWindow(QtWidgets.QDialog):
    """2Dプロット編集ウィンドウ。X-Y平面でキーを編集できる。"""

    def __init__(
        self,
        track: Track,
        key: Keyframe,
        on_update: Callable[[float, float], None],
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._track = track
        self._key = key
        self._on_update = on_update
        self._updating = False

        self.setWindowTitle(f"Edit Vector2 Key - {track.name}")
        self.setMinimumSize(400, 400)

        layout = QtWidgets.QVBoxLayout(self)

        # プロット
        self.plot = pg.PlotWidget(background="#2b2b2b")
        self.plot.showGrid(x=True, y=True, alpha=0.3)
        self.plot.setLabel("bottom", "X")
        self.plot.setLabel("left", "Y")
        self.plot.setAspectLocked(False)

        # 現在のキー位置
        vx = key.vx if key.vx is not None else 0.0
        vy = key.vy if key.vy is not None else 0.0
        self.current_point = pg.ScatterPlotItem(
            [vx],
            [vy],
            size=15,
            brush=pg.mkBrush(255, 160, 0, 220),
            pen=pg.mkPen(180, 100, 0, 220),
        )
        self.plot.addItem(self.current_point)

        # ドラッグ可能なポイント
        self.draggable_point = pg.ScatterPlotItem(
            [vx],
            [vy],
            size=12,
            brush=pg.mkBrush(40, 120, 255, 180),
            pen=pg.mkPen(0, 60, 160, 200),
        )
        self.plot.addItem(self.draggable_point)

        # 他のキーも表示（参考用）
        self.other_points = pg.ScatterPlotItem(
            size=8,
            brush=pg.mkBrush(100, 100, 100, 150),
            pen=pg.mkPen(80, 80, 80, 150),
        )
        self.plot.addItem(self.other_points)

        layout.addWidget(self.plot)

        # コントロール
        controls_layout = QtWidgets.QHBoxLayout()
        
        self.x_spin = QtWidgets.QDoubleSpinBox()
        self.x_spin.setRange(-1e9, 1e9)
        self.x_spin.setDecimals(6)
        self.x_spin.setSingleStep(0.1)
        self.x_spin.setValue(vx)
        self.x_spin.valueChanged.connect(self._on_x_changed)

        self.y_spin = QtWidgets.QDoubleSpinBox()
        self.y_spin.setRange(-1e9, 1e9)
        self.y_spin.setDecimals(6)
        self.y_spin.setSingleStep(0.1)
        self.y_spin.setValue(vy)
        self.y_spin.valueChanged.connect(self._on_y_changed)

        controls_layout.addWidget(QtWidgets.QLabel("X:"))
        controls_layout.addWidget(self.x_spin)
        controls_layout.addWidget(QtWidgets.QLabel("Y:"))
        controls_layout.addWidget(self.y_spin)
        controls_layout.addStretch()

        buttons_layout = QtWidgets.QHBoxLayout()
        self.btn_ok = QtWidgets.QPushButton("OK")
        self.btn_ok.clicked.connect(self.accept)
        self.btn_cancel = QtWidgets.QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        buttons_layout.addStretch()
        buttons_layout.addWidget(self.btn_ok)
        buttons_layout.addWidget(self.btn_cancel)

        layout.addLayout(controls_layout)
        layout.addLayout(buttons_layout)

        # ドラッグ処理
        self.plot.scene().installEventFilter(self)
        self._dragging = False
        self._drag_start_pos = None

        # 他のキーを表示
        self._update_other_points()

        # レンジを適切に設定
        self._fit_range()

    def _update_other_points(self) -> None:
        """他のキーを表示（参考用）。"""
        if self._track.track_type != TrackType.VECTOR2:
            return

        other_keys = [k for k in self._track.keys if k is not self._key]
        if not other_keys:
            self.other_points.setData([], [])
            return

        x_values = [k.vx if k.vx is not None else 0.0 for k in other_keys]
        y_values = [k.vy if k.vy is not None else 0.0 for k in other_keys]
        self.other_points.setData(x_values, y_values)

    def _fit_range(self) -> None:
        """プロットのレンジを適切に設定。"""
        if self._track.track_type != TrackType.VECTOR2:
            return

        all_keys = self._track.keys
        if not all_keys:
            self.plot.setXRange(-1.0, 1.0)
            self.plot.setYRange(-1.0, 1.0)
            return

        x_values = [k.vx if k.vx is not None else 0.0 for k in all_keys]
        y_values = [k.vy if k.vy is not None else 0.0 for k in all_keys]

        if not x_values or not y_values:
            self.plot.setXRange(-1.0, 1.0)
            self.plot.setYRange(-1.0, 1.0)
            return

        x_min, x_max = min(x_values), max(x_values)
        y_min, y_max = min(y_values), max(y_values)

        x_range = x_max - x_min
        y_range = y_max - y_min

        if x_range < 1e-6:
            x_min, x_max = x_min - 1.0, x_max + 1.0
        else:
            padding = x_range * 0.1
            x_min, x_max = x_min - padding, x_max + padding

        if y_range < 1e-6:
            y_min, y_max = y_min - 1.0, y_max + 1.0
        else:
            padding = y_range * 0.1
            y_min, y_max = y_min - padding, y_max + padding

        self.plot.setXRange(x_min, x_max)
        self.plot.setYRange(y_min, y_max)

    def eventFilter(self, obj, event) -> bool:
        """マウスイベントをフィルタリングしてドラッグ処理。"""
        if obj is not self.plot.scene():
            return super().eventFilter(obj, event)

        from PySide6.QtCore import QEvent
        from PySide6.QtGui import QMouseEvent

        if event.type() == QEvent.GraphicsSceneMousePress:
            if event.button() == QtCore.Qt.LeftButton:
                view_pos = self.plot.plotItem.vb.mapSceneToView(event.scenePos())
                # 現在のポイントに近いかチェック
                x = self.x_spin.value()
                y = self.y_spin.value()
                dist = ((view_pos.x() - x) ** 2 + (view_pos.y() - y) ** 2) ** 0.5
                # レンジに基づいて閾値を計算
                x_range = self.plot.plotItem.vb.viewRange()[0]
                y_range = self.plot.plotItem.vb.viewRange()[1]
                threshold = max((x_range[1] - x_range[0]), (y_range[1] - y_range[0])) * 0.05
                if dist < threshold:
                    self._dragging = True
                    self._drag_start_pos = event.scenePos()
                    return True

        elif event.type() == QEvent.GraphicsSceneMouseMove:
            if self._dragging:
                view_pos = self.plot.plotItem.vb.mapSceneToView(event.scenePos())
                self._update_position(view_pos.x(), view_pos.y())
                return True

        elif event.type() == QEvent.GraphicsSceneMouseRelease:
            if event.button() == QtCore.Qt.LeftButton:
                self._dragging = False
                self._drag_start_pos = None

        return super().eventFilter(obj, event)

    def _update_position(self, x: float, y: float) -> None:
        """位置を更新。"""
        self._updating = True
        try:
            self.x_spin.setValue(float(x))
            self.y_spin.setValue(float(y))
            self._update_plot()
            self._on_update(float(x), float(y))
        finally:
            self._updating = False

    def _on_x_changed(self, val: float) -> None:
        """X値が変更されたときの処理。"""
        if not self._updating:
            self._update_plot()
            self._on_update(float(val), self.y_spin.value())

    def _on_y_changed(self, val: float) -> None:
        """Y値が変更されたときの処理。"""
        if not self._updating:
            self._update_plot()
            self._on_update(self.x_spin.value(), float(val))

    def _update_plot(self) -> None:
        """プロットを更新。"""
        x = self.x_spin.value()
        y = self.y_spin.value()
        self.current_point.setData([x], [y])
        self.draggable_point.setData([x], [y])

