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
        
        # 基準レンジ（初期レンジ、ズーム計算の基準）
        self._base_x_range: tuple[float, float] = (-1.0, 1.0)
        self._base_y_range: tuple[float, float] = (-1.0, 1.0)
        # 現在のズームレベル（1.0が基準）
        self._zoom_level: float = 1.0
        # XY縮尺シンクロモード
        self._sync_xy_scale: bool = True

        self.setWindowTitle(f"Edit Vector2 Key - {track.name}")
        self.setMinimumSize(400, 400)

        layout = QtWidgets.QVBoxLayout(self)

        # プロット
        self.plot = pg.PlotWidget(background="#2b2b2b")
        self.plot.showGrid(x=True, y=True, alpha=0.3)
        # Trackのlabel_x/label_yを使用（なければ"X"/"Y"）
        label_x = track.label_x if track.label_x is not None else "X"
        label_y = track.label_y if track.label_y is not None else "Y"
        self.plot.setLabel("bottom", label_x)
        self.plot.setLabel("left", label_y)
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

        # Trackのlabel_x/label_yを使用（なければ"X"/"Y"）
        label_x = track.label_x if track.label_x is not None else "X"
        label_y = track.label_y if track.label_y is not None else "Y"
        controls_layout.addWidget(QtWidgets.QLabel(f"{label_x}:"))
        controls_layout.addWidget(self.x_spin)
        controls_layout.addWidget(QtWidgets.QLabel(f"{label_y}:"))
        controls_layout.addWidget(self.y_spin)
        controls_layout.addStretch()
        
        # 縮尺コントロール
        zoom_layout = QtWidgets.QHBoxLayout()
        zoom_layout.addWidget(QtWidgets.QLabel("Zoom:"))
        
        # 縮尺スライダー（0.1倍～10倍、1000段階で制御）
        self.zoom_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.zoom_slider.setMinimum(100)  # 0.1倍
        self.zoom_slider.setMaximum(10000)  # 10倍
        self.zoom_slider.setValue(1000)  # 1.0倍
        self.zoom_slider.setTickPosition(QtWidgets.QSlider.TickPosition.TicksBelow)
        self.zoom_slider.setTickInterval(1000)
        self.zoom_slider.valueChanged.connect(self._on_zoom_changed)
        zoom_layout.addWidget(self.zoom_slider)
        
        # ズーム値表示ラベル
        self.zoom_label = QtWidgets.QLabel("1.0x")
        self.zoom_label.setMinimumWidth(50)
        zoom_layout.addWidget(self.zoom_label)
        
        # XY縮尺シンクロモードスイッチ
        self.sync_xy_checkbox = QtWidgets.QCheckBox("Sync XY")
        self.sync_xy_checkbox.setChecked(True)
        self.sync_xy_checkbox.stateChanged.connect(self._on_sync_xy_changed)
        zoom_layout.addWidget(self.sync_xy_checkbox)
        
        # 視点リセットボタン
        self.reset_view_btn = QtWidgets.QPushButton("Reset View")
        self.reset_view_btn.clicked.connect(self._reset_view)
        zoom_layout.addWidget(self.reset_view_btn)
        
        controls_layout.addLayout(zoom_layout)

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
        
        # 基準レンジを保存
        x_range = self.plot.plotItem.vb.viewRange()[0]
        y_range = self.plot.plotItem.vb.viewRange()[1]
        self._base_x_range = (x_range[0], x_range[1])
        self._base_y_range = (y_range[0], y_range[1])

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
        
        # 基準レンジを更新
        self._base_x_range = (x_min, x_max)
        self._base_y_range = (y_min, y_max)
        self._zoom_level = 1.0
        # スライダーを1.0倍にリセット
        self.zoom_slider.setValue(1000)
        self.zoom_label.setText("1.0x")

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
    
    def _on_zoom_changed(self, value: int) -> None:
        """ズームスライダーが変更された時の処理。"""
        # スライダー値をズームレベルに変換（100 = 0.1倍、1000 = 1.0倍、10000 = 10倍）
        self._zoom_level = value / 1000.0
        self.zoom_label.setText(f"{self._zoom_level:.2f}x")
        
        # 基準レンジの中心を計算
        base_x_center = (self._base_x_range[0] + self._base_x_range[1]) / 2.0
        base_y_center = (self._base_y_range[0] + self._base_y_range[1]) / 2.0
        base_x_range = self._base_x_range[1] - self._base_x_range[0]
        base_y_range = self._base_y_range[1] - self._base_y_range[0]
        
        if self._sync_xy_scale:
            # シンクロモード: X/Yを同じ倍率で変更
            new_x_range = base_x_range / self._zoom_level
            new_y_range = base_y_range / self._zoom_level
            
            new_x_min = base_x_center - new_x_range / 2.0
            new_x_max = base_x_center + new_x_range / 2.0
            new_y_min = base_y_center - new_y_range / 2.0
            new_y_max = base_y_center + new_y_range / 2.0
            
            self.plot.setXRange(new_x_min, new_x_max)
            self.plot.setYRange(new_y_min, new_y_max)
        else:
            # 非シンクロモード: X/Yを独立して変更
            new_x_range = base_x_range / self._zoom_level
            new_y_range = base_y_range / self._zoom_level
            
            new_x_min = base_x_center - new_x_range / 2.0
            new_x_max = base_x_center + new_x_range / 2.0
            new_y_min = base_y_center - new_y_range / 2.0
            new_y_max = base_y_center + new_y_range / 2.0
            
            self.plot.setXRange(new_x_min, new_x_max)
            self.plot.setYRange(new_y_min, new_y_max)
    
    def _on_sync_xy_changed(self, state: int) -> None:
        """XY縮尺シンクロモードが変更された時の処理。"""
        self._sync_xy_scale = (state == QtCore.Qt.CheckState.Checked.value)
        # ズームレベルを再適用
        self._on_zoom_changed(self.zoom_slider.value())
    
    def _reset_view(self) -> None:
        """視点をリセット: 0,0と最遠点を含むレンジを設定。"""
        if self._track.track_type != TrackType.VECTOR2:
            return
        
        all_keys = self._track.keys
        if not all_keys:
            self.plot.setXRange(-1.0, 1.0)
            self.plot.setYRange(-1.0, 1.0)
            self._base_x_range = (-1.0, 1.0)
            self._base_y_range = (-1.0, 1.0)
            self._zoom_level = 1.0
            self.zoom_slider.setValue(1000)
            self.zoom_label.setText("1.0x")
            return
        
        # 0,0の点
        origin = (0.0, 0.0)
        
        # 全キーフレームから原点(0,0)からの距離が最大の点を計算
        max_distance = 0.0
        farthest_point = origin
        
        for key in all_keys:
            vx = key.vx if key.vx is not None else 0.0
            vy = key.vy if key.vy is not None else 0.0
            distance = (vx ** 2 + vy ** 2) ** 0.5
            if distance > max_distance:
                max_distance = distance
                farthest_point = (vx, vy)
        
        # 0,0と最遠点を含む最小の矩形を計算
        x_values = [0.0, farthest_point[0]]
        y_values = [0.0, farthest_point[1]]
        
        x_min, x_max = min(x_values), max(x_values)
        y_min, y_max = min(y_values), max(y_values)
        
        # 余白を追加（10%）
        x_range = x_max - x_min
        y_range = y_max - y_min
        
        if x_range < 1e-6:
            x_min, x_max = -1.0, 1.0
        else:
            padding = x_range * 0.1
            x_min -= padding
            x_max += padding
        
        if y_range < 1e-6:
            y_min, y_max = -1.0, 1.0
        else:
            padding = y_range * 0.1
            y_min -= padding
            y_max += padding
        
        # レンジを設定
        self.plot.setXRange(x_min, x_max)
        self.plot.setYRange(y_min, y_max)
        
        # 基準レンジを更新
        self._base_x_range = (x_min, x_max)
        self._base_y_range = (y_min, y_max)
        self._zoom_level = 1.0
        # スライダーを1.0倍にリセット
        self.zoom_slider.setValue(1000)
        self.zoom_label.setText("1.0x")

