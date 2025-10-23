from __future__ import annotations
from typing import Optional, Set, List
from PySide6 import QtWidgets, QtCore
from PySide6.QtCore import QTimer, QEvent, QPointF, QRectF
import pyqtgraph as pg
import numpy as np

from ..core.timeline import Timeline, Keyframe, InterpMode
from ..core.interpolation import evaluate
from ..io.csv_exporter import export_csv


class MainWindow(QtWidgets.QMainWindow):
    """
    Timeline Editor (P0) — Mouse spec:
      Left click:
        - single: on point -> select; empty -> if selected: clear; else move playhead (no scaling)
        - double: add key at cursor (no scaling)
        - drag: on point -> move; empty -> marquee select (no scaling)
      Wheel:
        - drag (middle button): pan (default)
        - rotate: zoom equally on X/Y
      Right click:
        - single: context menu
        - drag: keep pyqtgraph default (aspect change)
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Timeline Editor (P0, mouse spec)")
        self.resize(1200, 740)

        # --- Model & state ---
        self.timeline = Timeline()
        self.sample_rate = 90.0

        # Selection is a set of Keyframe objects (stable across resort)
        self._selection: Set[int] = set()
        self._dragging_key: Optional[int] = None
        self._marquee_active: bool = False
        self._marquee_start_scene: Optional[QPointF] = None
        self._marquee_rect_item: Optional[QtWidgets.QGraphicsRectItem] = None

        # --- Plot setup ---
        self.plot = pg.PlotWidget(background="w")
        self.plot.showGrid(x=True, y=True, alpha=0.25)
        self.plot.setLabel("bottom", "Time (s)")
        self.plot.setLabel("left", "Value")
        vb = self.plot.plotItem.vb
        vb.enableAutoRange(x=False, y=False)  # 自動レンジを完全停止（勝手に変えない）

        # Curve + key points
        self.curve_item = self.plot.plot([], [], pen=pg.mkPen(0, 0, 0, 220, width=2))
        self.points = pg.ScatterPlotItem(
            size=10,
            brush=pg.mkBrush(40, 120, 255, 180),
            pen=pg.mkPen(0, 60, 160, 200)
        )
        self.plot.addItem(self.points)

        # Playhead
        self.playhead = pg.InfiniteLine(pos=0.0, angle=90, movable=False, pen=pg.mkPen(200, 0, 0, 200))
        self.plot.addItem(self.playhead)

        # --- Toolbar ---
        tb = QtWidgets.QToolBar()
        self.addToolBar(tb)

        self.mode_combo = QtWidgets.QComboBox()
        self.mode_combo.addItems(["cubic", "linear", "step"])
        tb.addWidget(QtWidgets.QLabel("Interpolation: "))
        tb.addWidget(self.mode_combo)

        tb.addSeparator()
        self.duration = QtWidgets.QDoubleSpinBox()
        self.duration.setRange(0.1, 10000.0)
        self.duration.setValue(self.timeline.duration_s)
        self.duration.setSuffix(" s")
        tb.addWidget(QtWidgets.QLabel("Duration: "))
        tb.addWidget(self.duration)

        self.rate = QtWidgets.QDoubleSpinBox()
        self.rate.setRange(1.0, 1000.0)
        self.rate.setDecimals(1)
        self.rate.setValue(self.sample_rate)
        self.rate.setSuffix(" Hz")
        tb.addWidget(QtWidgets.QLabel("Sample: "))
        tb.addWidget(self.rate)

        tb.addSeparator()
        self.btn_add = QtWidgets.QPushButton("Add Key @Cursor")
        self.btn_del = QtWidgets.QPushButton("Delete Selected")
        self.btn_reset = QtWidgets.QPushButton("Reset")
        tb.addWidget(self.btn_add); tb.addWidget(self.btn_del); tb.addWidget(self.btn_reset)

        tb.addSeparator()
        self.btn_export = QtWidgets.QPushButton("Export CSV")
        tb.addWidget(self.btn_export)

        tb.addSeparator()
        self.btn_play = QtWidgets.QPushButton("▶")
        self.btn_stop = QtWidgets.QPushButton("■")
        tb.addWidget(self.btn_play); tb.addWidget(self.btn_stop)

        tb.addSeparator()
        self.btn_fitx = QtWidgets.QPushButton("Fit X")
        self.btn_fity = QtWidgets.QPushButton("Fit Y")
        tb.addWidget(self.btn_fitx); tb.addWidget(self.btn_fity)

        # Central
        central = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(central)
        lay.addWidget(self.plot)
        self.setCentralWidget(central)
        self.setStatusBar(QtWidgets.QStatusBar())

        # Timer (playback)
        self.timer = QTimer()
        self.timer.timeout.connect(self.on_tick)
        self.t0: Optional[QtCore.QTime] = None

        # Scene event filter for mouse spec
        self.plot.scene().installEventFilter(self)

        # Signals
        self.mode_combo.currentIndexChanged.connect(self.on_mode)
        self.duration.valueChanged.connect(self.on_duration)
        self.rate.valueChanged.connect(self.on_rate)
        self.btn_add.clicked.connect(self.add_key_at_cursor)
        self.btn_del.clicked.connect(self.delete_selected)
        self.btn_reset.clicked.connect(self.reset_keys)
        self.btn_export.clicked.connect(self.do_export)
        self.btn_play.clicked.connect(self.play)
        self.btn_stop.clicked.connect(self.stop)
        self.btn_fitx.clicked.connect(self.fit_x)
        self.btn_fity.clicked.connect(self.fit_y)

        # Initial draw & fit
        self.update_plot()
        self.fit_x()
        self.fit_y(padding=0.15)
        
        self._rc_press_scene = None
        self._rc_dragging = False
        self._rc_drag_thresh_px = 6

        self._mid_panning = False
        self._mid_last_scene = None

        self._mid_panning = False
        self._mid_last_scene = None
        self._rc_press_scene = None
        self._rc_dragging = False
        self._rc_drag_thresh = 6  # px

        self._left_down = False
        self._dragging_key = None
        self._marquee_active = False
        self._marquee_start_scene = None
        self._marquee_rect_item = None

        self._rc_press_scene = None
        self._rc_dragging = False
        self._rc_pivot_view = None
        self._rc_last_scene = None
        self._rc_drag_thresh_px = 6
        self._rc_zoom_sensitivity = 0.002

        self.plot.scene().installEventFilter(self)

    # -------------------- UI Helpers --------------------
    def _viewbox(self) -> pg.ViewBox:
        return self.plot.plotItem.vb

    def _scene_to_view(self, scene_pos: QPointF) -> QPointF:
        return self._viewbox().mapSceneToView(scene_pos)

    def _view_to_scene(self, view_pos: QPointF) -> QPointF:
        return self._viewbox().mapViewToScene(view_pos)

    def _all_keys(self) -> List[int]:
        return self.timeline.track.sorted()

    # -------------------- Mouse Policy (eventFilter) --------------------
    def eventFilter(self, obj, ev):
        if obj is not self.plot.scene():
            return super().eventFilter(obj, ev)

        # --- 左クリック ---
        # ===== 左ボタン：選択/移動/範囲選択（≠ズーム） =====
        if ev.type() == QtCore.QEvent.GraphicsSceneMousePress and ev.button() == QtCore.Qt.LeftButton:
            self._left_down = True
            idx = self._hit_test_key(ev.scenePos(), px_thresh=10)
            if idx is not None:
                # 点の上 → その点を掴む
                ks_sorted = self.timeline.track.sorted()
                self._dragging_key = ks_sorted[idx]
            else:
                # 点が無い → 既に選択があれば解除、無ければプレイヘッド移動
                if getattr(self, "_selection", None):
                    self._selection.clear()
                    self.update_plot()
                else:
                    vp = self.plot.plotItem.vb.mapSceneToView(ev.scenePos())
                    self.playhead.setValue(max(0.0, float(vp.x())))
                # ドラッグに移行したらラバーバンド開始
                self._marquee_active = False
                self._marquee_start_scene = ev.scenePos()
            return True  # ★既定(矩形ズーム)を完全にブロック

        if ev.type() == QtCore.QEvent.GraphicsSceneMouseDoubleClick and ev.button() == QtCore.Qt.LeftButton:
            # クリック位置そのままに点追加
            vp = self.plot.plotItem.vb.mapSceneToView(ev.scenePos())
            kf = Keyframe(float(max(0.0, vp.x())), float(vp.y()))
            self.timeline.track.keys.append(kf)
            self.timeline.track.clamp_times()
            if getattr(self, "_selection", None) is not None:
                self._selection = {id(kf)}
            self.update_plot()
            return True  # ★既定無効

        if ev.type() == QtCore.QEvent.GraphicsSceneMouseMove and self._left_down:
            if self._dragging_key is not None:
                # 点を移動（オートパン任意）
                vb = self.plot.plotItem.vb
                mp = vb.mapSceneToView(ev.scenePos())
                self._dragging_key.t = float(max(0.0, mp.x()))
                self._dragging_key.v = float(mp.y())
                self.timeline.track.clamp_times()
                # 端でオートパン：必要なら有効化
                # self._auto_pan_if_close_to_edge(ev.scenePos(), margin_px=24, step_frac=0.03)
                self.update_plot()
                return True  # ★既定無効

            # 空間ドラッグ → 範囲選択（ラバーバンド）
            if not self._marquee_active and self._marquee_start_scene is not None:
                self._marquee_active = True
                rect = QtWidgets.QGraphicsRectItem()
                rect.setPen(pg.mkPen(0, 120, 255, 180, width=1))
                rect.setBrush(pg.mkBrush(0, 120, 255, 40))
                self.plot.scene().addItem(rect)
                self._marquee_rect_item = rect

            if self._marquee_active:
                r = QtCore.QRectF(self._marquee_start_scene, ev.scenePos()).normalized()
                self._marquee_rect_item.setRect(r)
            return True  # ★既定無効

        if ev.type() == QtCore.QEvent.GraphicsSceneMouseRelease and ev.button() == QtCore.Qt.LeftButton:
            # ドラッグ終了
            if self._dragging_key is not None:
                self._dragging_key = None

            # 範囲選択確定
            if self._marquee_active and self._marquee_rect_item is not None:
                rect = self._marquee_rect_item.rect()
                vb = self.plot.plotItem.vb
                selected_ids = set()
                for k in self.timeline.track.sorted():
                    sp = vb.mapViewToScene(QtCore.QPointF(k.t, k.v))
                    if rect.contains(sp):
                        selected_ids.add(id(k))
                if getattr(self, "_selection", None) is not None:
                    self._selection = selected_ids
                # 後片付け
                self.plot.scene().removeItem(self._marquee_rect_item)
                self._marquee_rect_item = None
                self._marquee_active = False
                self._marquee_start_scene = None
                self.update_plot()

            self._left_down = False
            return True  # ★既定無効

        # --- 中ボタンドラッグ（パン固定） ---
        if ev.type() == QtCore.QEvent.GraphicsSceneMousePress and ev.button() == QtCore.Qt.MiddleButton:
            self._mid_panning = True
            self._mid_last_scene = ev.scenePos()
            return True
        if ev.type() == QtCore.QEvent.GraphicsSceneMouseMove and getattr(self, "_mid_panning", False):
            vb = self.plot.plotItem.vb
            if self._mid_last_scene is not None:
                v0 = vb.mapSceneToView(self._mid_last_scene)
                v1 = vb.mapSceneToView(ev.scenePos())
                vb.translateBy(x=-(v1.x()-v0.x()), y=-(v1.y()-v0.y()))
            self._mid_last_scene = ev.scenePos()
            return True
        if ev.type() == QtCore.QEvent.GraphicsSceneMouseRelease and ev.button() == QtCore.Qt.MiddleButton:
            self._mid_panning = False
            self._mid_last_scene = None
            return True

        # --- 右クリック（ドラッグ＝拡縮／クリック＝メニュー） ---
        if ev.type() == QtCore.QEvent.GraphicsSceneMousePress and ev.button() == QtCore.Qt.RightButton:
            vb = self.plot.plotItem.vb
            self._rc_press_scene = ev.scenePos()
            self._rc_last_scene  = ev.scenePos()
            self._rc_pivot_view  = vb.mapSceneToView(ev.scenePos())  # ★押下位置を不動点に
            self._rc_dragging    = False
            return True  # 以降は自前で処理（既定を無効化）

        if ev.type() == QtCore.QEvent.GraphicsSceneMouseMove and (QtWidgets.QApplication.mouseButtons() & QtCore.Qt.RightButton):
            if self._rc_press_scene is None:
                return True
            vb = self.plot.plotItem.vb
            cur = ev.scenePos()
            # ドラッグ判定
            if not self._rc_dragging and (cur - self._rc_press_scene).manhattanLength() > self._rc_drag_thresh_px:
                self._rc_dragging = True

            # ★pivot（押下位置）を中心に、相対移動量から縦横別スケールを累積適用
            #   右方向に動かすとX拡大、左でX縮小
            #   上方向でY拡大、下でY縮小（好みで符号を反転して調整）
            dx_px = cur.x() - self._rc_last_scene.x()
            dy_px = cur.y() - self._rc_last_scene.y()
            s = self._rc_zoom_sensitivity
            sx = float(np.exp(-s * dx_px))
            sy = float(np.exp(+s * dy_px))  # 画面座標は上が小さいので符号を反転

            # 係数が極端にならないようにクランプ（任意）
            sx = max(0.2, min(5.0, sx))
            sy = max(0.2, min(5.0, sy))

            vb.scaleBy((sx, sy), center=self._rc_pivot_view)
            self._rc_last_scene = cur
            return True  # 既定無効（パンが混ざらない）

        if ev.type() == QtCore.QEvent.GraphicsSceneMouseRelease and ev.button() == QtCore.Qt.RightButton:
            # ドラッグでなければコンテキストメニュー
            if not self._rc_dragging:
                menu = QtWidgets.QMenu(self)
                act_add = menu.addAction("Add Key Here")
                act_del = menu.addAction("Delete Nearest")
                act = menu.exec(ev.screenPos())
                if act is act_add:
                    vp = self.plot.plotItem.vb.mapSceneToView(ev.scenePos())
                    self.timeline.track.keys.append(Keyframe(float(max(0.0, vp.x())), float(vp.y())))
                    self.timeline.track.clamp_times()
                    if getattr(self, "_selection", None) is not None:
                        self._selection = {id(self.timeline.track.keys[-1])}
                    self.update_plot()
                elif act is act_del:
                    self.delete_nearest_key()
            # 後片付け
            self._rc_press_scene = None
            self._rc_last_scene  = None
            self._rc_pivot_view  = None
            self._rc_dragging    = False
            return True

        return super().eventFilter(obj, ev)


    # -------------------- Hit test & marquee --------------------
    def _hit_test_key(self, scene_pos: QPointF, px_thresh: int = 10) -> Optional[int]:
        """Return index in sorted keys if within px_thresh of a point, else None."""
        ks = self._all_keys()
        if not ks:
            return None
        vb = self._viewbox()
        best_i = None
        best_d = 1e9
        for i, k in enumerate(ks):
            sp = vb.mapViewToScene(QPointF(k.t, k.v))
            d = (sp - scene_pos).manhattanLength()
            if d < best_d:
                best_d = d
                best_i = i
        return best_i if best_d <= px_thresh else None

    def _update_marquee(self, scene_pos: QPointF):
        if not self._marquee_active:
            # start marquee
            self._marquee_active = True
            self._marquee_start_scene = scene_pos
            rect = QtWidgets.QGraphicsRectItem()
            rect.setPen(pg.mkPen(0, 120, 255, 180, width=1))
            rect.setBrush(pg.mkBrush(0, 120, 255, 40))
            self.plot.scene().addItem(rect)
            self._marquee_rect_item = rect

        # update rect
        sp0 = self._marquee_start_scene
        r = QRectF(sp0, scene_pos).normalized()
        self._marquee_rect_item.setRect(r)

    def _commit_marquee_selection(self):
        if not self._marquee_active:
            return
        rect = self._marquee_rect_item.rect()
        vb = self._viewbox()
        selected: Set[int] = set()
        for k in self._all_keys():
            sp = vb.mapViewToScene(QPointF(k.t, k.v))
            if rect.contains(sp):
                selected.add(id(k))
        self._selection = selected
        # cleanup
        self.plot.scene().removeItem(self._marquee_rect_item)
        self._marquee_rect_item = None
        self._marquee_active = False
        self._marquee_start_scene = None
        self.update_plot()

    # -------------------- Context menu --------------------
    def _show_context_menu(self, screen_pos: QtCore.QPoint, scene_pos: QPointF):
        menu = QtWidgets.QMenu(self)
        act_add = menu.addAction("Add Key Here")
        act_del = menu.addAction("Delete Selected")
        menu.addSeparator()
        sub_interp = menu.addMenu("Interpolation")
        a_cubic = sub_interp.addAction("cubic")
        a_linear = sub_interp.addAction("linear")
        a_step = sub_interp.addAction("step")

        act = menu.exec(screen_pos)
        if act is None:
            return

        if act is act_add:
            self._add_key_at_scene(scene_pos)
        elif act is act_del:
            self.delete_selected()
        elif act in (a_cubic, a_linear, a_step):
            txt = act.text()
            self.timeline.track.interp = {
                "cubic": InterpMode.CUBIC,
                "linear": InterpMode.LINEAR,
                "step": InterpMode.STEP
            }[txt]
            self.update_plot()

    # -------------------- Add / Delete / Export --------------------
    def _add_key_at_scene(self, scene_pos: QPointF):
        vp = self._scene_to_view(scene_pos)
        t = float(max(0.0, vp.x()))
        # sample current curve value for initial y
        v = float(evaluate(self.timeline.track, np.array([t]))[0])
        kf = Keyframe(t, v)
        self.timeline.track.keys.append(kf)
        self.timeline.track.clamp_times()
        self._selection = {id(kf)}
        self.update_plot()

    def add_key_at_cursor(self):
        # convenience toolbar button: add at current playhead
        t = float(self.playhead.value())
        v = float(evaluate(self.timeline.track, np.array([t]))[0])
        kf = Keyframe(t, v)
        self.timeline.track.keys.append(kf)
        self.timeline.track.clamp_times()
        self._selection = {id(kf)}
        self.update_plot()

    def delete_selected(self):
        if not self._selection:
            return
        self.timeline.track.keys = [k for k in self.timeline.track.keys if id(k) not in self._selection]
        self._selection.clear()
        self.update_plot()

    def do_export(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Export CSV", "timeline.csv", "CSV Files (*.csv)")
        if not path:
            return
        export_csv(path, self.timeline, self.sample_rate)
        QtWidgets.QMessageBox.information(self, "Export", f"Exported to:\n{path}")

    # -------------------- Playback --------------------
    def play(self):
        self.t0 = QtCore.QTime.currentTime()
        self.timer.start(int(1000 / 60))

    def stop(self):
        self.timer.stop()

    def on_tick(self):
        if self.t0 is None:
            return
        elapsed = self.t0.msecsTo(QtCore.QTime.currentTime()) / 1000.0
        t = elapsed % max(1e-6, self.timeline.duration_s)
        self.playhead.setValue(t)

    # -------------------- Plot update & ranges --------------------
    def update_plot(self):
        # curve
        ks = self._all_keys()
        tmax = max(self.timeline.duration_s, max((k.t for k in ks), default=0.0))
        dense_t = np.linspace(0.0, max(1e-3, tmax), 1200)
        dense_v = evaluate(self.timeline.track, dense_t)
        self.curve_item.setData(dense_t, dense_v)

        # points (selected ones highlighted)
        spots = []
        for k in ks:
            is_sel = (id(k) in self._selection)
            spots.append({
                "pos": (k.t, k.v),
                "data": id(k),  # not used for hit, but unique
                "brush": pg.mkBrush(255, 160, 0, 220) if is_sel else pg.mkBrush(40, 120, 255, 180),
                "size": 12 if is_sel else 10,
                "pen": pg.mkPen(180, 100, 0, 220) if is_sel else pg.mkPen(0, 60, 160, 200),
            })
        self.points.setData(spots)

    def fit_x(self, padding: float = 0.02):
        vb = self._viewbox()
        ks = self._all_keys()
        tmax = max(self.timeline.duration_s, max((k.t for k in ks), default=0.0))
        vb.setXRange(0.0, max(1.0, tmax), padding=padding)

    def fit_y(self, padding: float = 0.05):
        vb = self._viewbox()
        ks = self._all_keys()
        if ks:
            vmin = min(k.v for k in ks)
            vmax = max(k.v for k in ks)
        else:
            vmin = -1.0
            vmax = 1.0
        if not np.isfinite(vmin) or not np.isfinite(vmax) or abs(vmax - vmin) < 1e-6:
            c = 0.5 * (vmin + vmax)
            vmin, vmax = c - 1.0, c + 1.0
        pad = padding * (vmax - vmin)
        vb.setYRange(vmin - pad, vmax + pad, padding=0)

    # -------------------- Zoom / Pan helpers --------------------
    def _zoom_equal_axes(self, ev):
        """Mouse wheel: zoom equally on X/Y around cursor."""
        # angleDelta().y(): positive for wheel up
        delta = ev.angleDelta().y() if hasattr(ev, "angleDelta") else getattr(ev, "delta", lambda: 0)()
        if delta == 0:
            return
        s = 0.9 if delta > 0 else 1.1  # <1 zoom-in, >1 zoom-out
        vb = self._viewbox()
        center = self._scene_to_view(ev.scenePos())
        vb.scaleBy((s, s), center=center)

    def _auto_pan_if_close_to_edge(self, scene_pos: QPointF, margin_px: int = 24, step_frac: float = 0.03):
        """While dragging a point, if cursor is near view edge, pan the view."""
        vb = self._viewbox()
        view_rect = vb.viewRect()
        # Compute in scene px space:
        sr = self.plot.sceneRect()
        x = scene_pos.x(); y = scene_pos.y()
        dx = step_frac * view_rect.width()
        dy = step_frac * view_rect.height()

        pan_x = 0.0; pan_y = 0.0
        if x - sr.left() < margin_px:
            pan_x = -dx
        elif sr.right() - x < margin_px:
            pan_x = +dx
        if y - sr.top() < margin_px:
            pan_y = +dy
        elif sr.bottom() - y < margin_px:
            pan_y = -dy

        if pan_x or pan_y:
            vb.translateBy(x=pan_x, y=pan_y)

    # -------------------- Slots --------------------
    def on_mode(self, idx):
        text = self.mode_combo.currentText()
        self.timeline.track.interp = {
            "cubic": InterpMode.CUBIC,
            "linear": InterpMode.LINEAR,
            "step": InterpMode.STEP
        }[text]
        self.update_plot()

    def on_duration(self, val):
        self.timeline.set_duration(float(val))
        # Xのみ明示的にフィット（勝手に変えない方針）
        self.fit_x()
        self.update_plot()

    def on_rate(self, val):
        self.sample_rate = float(val)

    def reset_keys(self):
        """初期状態にリセット（0秒=0, Duration秒=0 の2点）"""
        self.timeline.track.keys.clear()
        self.timeline.track.keys.append(Keyframe(0.0, 0.0))
        self.timeline.track.keys.append(Keyframe(self.timeline.duration_s, 0.0))
        self._selection.clear()
        self.update_plot()

    