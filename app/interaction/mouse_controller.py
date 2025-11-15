# interaction/mouse_controller.py
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional, Callable
import numpy as np
from PySide6 import QtCore, QtWidgets
from PySide6.QtCore import QPointF
import pyqtgraph as pg

from ..core.timeline import Timeline, Keyframe, Track
from ..core.interpolation import evaluate
from .selection import SelectionManager, KeyPoint, KeyPosProvider


logger = logging.getLogger(__name__)


@dataclass
class KeyDragState:
    """State container for keyframe drag operations."""

    key_point: Optional[KeyPoint] = None
    start_tv: tuple[float, float] | None = None

    @property
    def active(self) -> bool:
        return self.key_point is not None

    def reset(self) -> None:
        self.key_point = None
        self.start_tv = None


@dataclass
class ZoomDragState:
    """State container for right button zoom drag operations."""

    press_scene: Optional[QPointF] = None
    last_scene: Optional[QPointF] = None
    pivot_view: Optional[QPointF] = None
    dragging: bool = False

    @property
    def active(self) -> bool:
        return self.press_scene is not None

    def reset(self) -> None:
        self.press_scene = None
        self.last_scene = None
        self.pivot_view = None
        self.dragging = False


class MouseController(QtCore.QObject):
    """
    マウス操作のポリシー実装（P0）
      - 左: 点ヒット => ドラッグ移動 / 非ヒット => マルキー開始 or プレイヘッド移動
      - 中: パン
      - 右: ドラッグズーム（押下位置をピボット） / クリックで簡易メニュー
    視覚面の更新は on_changed() コールバックで呼び出し元に委譲。
    """

    def __init__(
        self,
        plot_widget: pg.PlotWidget,
        timeline: Timeline,
        selection: SelectionManager,
        pos_provider: KeyPosProvider,
        on_changed: Callable[[], None],
        set_playhead: Callable[[float], None],
        commit_drag: Optional[Callable[[Keyframe, tuple, tuple], None]] = None,
        # ▼ 追加：右クリック/ダブルクリック用のコールバック
        add_key_cb: Optional[Callable[[float, float], Optional[Keyframe]]] = None,
        delete_key_cb: Optional[Callable[[Keyframe], None]] = None,
    ):
        super().__init__()
        self.plot = plot_widget
        self.timeline = timeline
        self.sel = selection
        self.provider = pos_provider
        self.on_changed = on_changed
        self.set_playhead = set_playhead

        # 状態
        self._left_down = False
        self._key_drag = KeyDragState()

        # 中ボタンパン
        self._mid_panning = False
        self._mid_last_scene: Optional[QPointF] = None

        # 右ドラッグズーム
        self._zoom_drag = ZoomDragState()
        self._rc_drag_thresh_px = 6
        self._rc_zoom_sensitivity = 0.002

        # イベントフック
        self.plot.scene().installEventFilter(self)

        self.commit_drag = commit_drag
        self.add_key_cb = add_key_cb
        self.delete_key_cb = delete_key_cb

    def set_plot_widget(self, plot_widget: pg.PlotWidget) -> None:
        if self.plot is plot_widget:
            return
        try:
            self.plot.scene().removeEventFilter(self)
        except Exception:
            pass
        self.plot = plot_widget
        self.plot.scene().installEventFilter(self)

    # ---- ショートカット ----
    @property
    def vb(self) -> pg.ViewBox:
        return self.plot.plotItem.vb

    def _scene_to_view(self, p: QPointF) -> QPointF:
        return self.vb.mapSceneToView(p)

    # ---- KeyPoint -> Keyframe 解決（単一トラック前提の簡易版）----
    def _track_for_id(self, track_id: str) -> Optional[Track]:
        for track in self.timeline.iter_tracks():
            if track.track_id == track_id:
                return track
        return None

    def _resolve_key(self, kp: KeyPoint) -> Optional[Keyframe]:
        track = self._track_for_id(kp.track_id)
        if track is None:
            return None
        for k in track.keys:
            if id(k) == kp.key_id:
                return k
        return None

    # ============================================================
    # Event filter
    # ============================================================
    def eventFilter(self, obj, ev):
        if obj is not self.plot.scene():
            return super().eventFilter(obj, ev)

        et = ev.type()
        Qt = QtCore.Qt

        if et == QtCore.QEvent.GraphicsSceneMousePress:
            if ev.button() == Qt.LeftButton:
                return self._handle_left_button_press(ev)
            if ev.button() == Qt.MiddleButton:
                return self._handle_middle_button_press(ev)
            if ev.button() == Qt.RightButton:
                return self._handle_right_button_press(ev)

        if et == QtCore.QEvent.GraphicsSceneMouseMove:
            handled = False
            handled = self._handle_left_button_move(ev) or handled
            handled = self._handle_middle_button_move(ev) or handled
            handled = self._handle_right_button_move(ev) or handled
            if handled:
                return True

        if et == QtCore.QEvent.GraphicsSceneMouseRelease:
            if ev.button() == Qt.LeftButton:
                return self._handle_left_button_release(ev)
            if ev.button() == Qt.MiddleButton:
                return self._handle_middle_button_release(ev)
            if ev.button() == Qt.RightButton:
                return self._handle_right_button_release(ev)

        if et == QtCore.QEvent.GraphicsSceneMouseDoubleClick and ev.button() == Qt.LeftButton:
            return self._handle_left_button_double_click(ev)

        if et == QtCore.QEvent.GraphicsSceneWheel:
            return self._handle_wheel(ev)

        return super().eventFilter(obj, ev)

    # ============================================================
    # Helpers
    # ============================================================
    def _is_shift(self, ev: QtWidgets.QGraphicsSceneMouseEvent) -> bool:
        return bool(ev.modifiers() & QtCore.Qt.ShiftModifier)

    # ---- Event handlers -------------------------------------------------
    def _handle_left_button_press(self, ev: QtWidgets.QGraphicsSceneMouseEvent) -> bool:
        """Handle left button press by selecting keys or starting marquee."""

        self._left_down = True
        hit = self.sel.hit_test_nearest(ev.scenePos(), px_thresh=10)
        if hit is not None:
            if self._is_shift(ev):
                self.sel.add(hit.track_id, hit.key_id)
            else:
                self.sel.set_single(hit.track_id, hit.key_id)
            self._begin_key_drag(hit)
            self.on_changed()
        else:
            if self.sel.selected:
                self.sel.clear()
                self.on_changed()
            else:
                vp = self._scene_to_view(ev.scenePos())
                self.set_playhead(max(0.0, float(vp.x())))
            self.sel.marquee_begin(ev.scenePos())
        return True

    def _handle_left_button_move(self, ev: QtWidgets.QGraphicsSceneMouseEvent) -> bool:
        """Handle mouse move while the left button is pressed."""

        if not self._left_down:
            return False
        if self._update_key_drag(ev.scenePos()):
            return True
        self.sel.marquee_update(ev.scenePos())
        self.on_changed()
        return True

    def _handle_left_button_release(self, ev: QtWidgets.QGraphicsSceneMouseEvent) -> bool:
        """Handle left button release by finalising drags or marquee."""

        self._left_down = False
        self._end_key_drag()
        self.sel.marquee_commit(additive=self._is_shift(ev))
        self.on_changed()
        return True

    def _handle_left_button_double_click(self, ev: QtWidgets.QGraphicsSceneMouseEvent) -> bool:
        """Handle double click by adding a key at the cursor position."""

        vp = self._scene_to_view(ev.scenePos())
        t = float(max(0.0, vp.x()))
        v = float(vp.y())
        kf = self._create_keyframe(t, v)
        if kf is not None:
            self.sel.set_single(self.provider.track_id, id(kf))
            self.on_changed()
        return True

    def _handle_middle_button_press(self, ev: QtWidgets.QGraphicsSceneMouseEvent) -> bool:
        """Handle middle button press by preparing for panning."""

        self._mid_panning = True
        self._mid_last_scene = ev.scenePos()
        return True

    def _handle_middle_button_move(self, ev: QtWidgets.QGraphicsSceneMouseEvent) -> bool:
        """Handle mouse move while the middle button is pressed for panning."""

        if not self._mid_panning:
            return False
        if self._mid_last_scene is not None:
            v0 = self._scene_to_view(self._mid_last_scene)
            v1 = self._scene_to_view(ev.scenePos())
            self.vb.translateBy(x=-(v1.x() - v0.x()), y=-(v1.y() - v0.y()))
        self._mid_last_scene = ev.scenePos()
        return True

    def _handle_middle_button_release(self, _ev: QtWidgets.QGraphicsSceneMouseEvent) -> bool:
        """Handle middle button release by ending panning."""

        self._mid_panning = False
        self._mid_last_scene = None
        return True

    def _handle_right_button_press(self, ev: QtWidgets.QGraphicsSceneMouseEvent) -> bool:
        """Handle right button press by preparing drag zoom."""

        self._begin_zoom_drag(ev.scenePos())
        return True

    def _handle_right_button_move(self, ev: QtWidgets.QGraphicsSceneMouseEvent) -> bool:
        """Handle right button drag to zoom around the pivot point."""

        if not (QtWidgets.QApplication.mouseButtons() & QtCore.Qt.RightButton):
            return False
        return self._update_zoom_drag(ev.scenePos())

    def _handle_right_button_release(self, ev: QtWidgets.QGraphicsSceneMouseEvent) -> bool:
        """Handle right button release by finalising zoom or opening a menu."""

        if not self._zoom_drag.active:
            return False
        if not self._zoom_drag.dragging:
            self._show_context_menu(ev)
        self._end_zoom_drag()
        return True

    def _handle_wheel(self, ev: QtWidgets.QGraphicsSceneWheelEvent) -> bool:
        """Handle wheel event to perform uniform zoom around the cursor."""

        delta = ev.delta() if hasattr(ev, "delta") else ev.angleDelta().y()
        if not delta:
            return False
        s = 0.9 if delta > 0 else 1.1
        center = self._scene_to_view(ev.scenePos())
        self.vb.scaleBy((s, s), center=center)
        return True

    # ---- Drag helpers ---------------------------------------------------
    def _begin_key_drag(self, hit: KeyPoint) -> None:
        """Initialise state for dragging the key represented by ``hit``."""

        self._key_drag.key_point = hit
        key = self._resolve_key(hit)
        if key is not None:
            self._key_drag.start_tv = (key.t, key.v)
        else:
            self._key_drag.start_tv = None

    def _update_key_drag(self, scene_pos: QPointF) -> bool:
        """Update the key drag to follow ``scene_pos`` if active."""

        if not self._key_drag.active:
            return False
        key_point = self._key_drag.key_point
        if key_point is None:
            return False
        key = self._resolve_key(key_point)
        if key is None:
            return False
        mp = self._scene_to_view(scene_pos)
        key.t = float(max(0.0, mp.x()))
        key.v = float(mp.y())
        track = self._track_for_id(key_point.track_id)
        if track is not None:
            track.clamp_times()
        self.on_changed()
        return True

    def _end_key_drag(self) -> bool:
        """Finalize the current key drag and issue commit callbacks."""

        if not self._key_drag.active:
            return False
        key_point = self._key_drag.key_point
        key = self._resolve_key(key_point) if key_point is not None else None
        if (
            key is not None
            and self.commit_drag is not None
            and self._key_drag.start_tv is not None
        ):
            t0, v0 = self._key_drag.start_tv
            t1, v1 = key.t, key.v
            if abs(t0 - t1) > 1e-12 or abs(v0 - v1) > 1e-12:
                self.commit_drag(key, (t0, v0), (t1, v1))
        self._key_drag.reset()
        return True

    def _begin_zoom_drag(self, scene_pos: QPointF) -> None:
        """Initialise the right button zoom drag state."""

        self._zoom_drag.press_scene = scene_pos
        self._zoom_drag.last_scene = scene_pos
        self._zoom_drag.pivot_view = self._scene_to_view(scene_pos)
        self._zoom_drag.dragging = False

    def _update_zoom_drag(self, scene_pos: QPointF) -> bool:
        """Update the zoom drag operation based on the current cursor position."""

        if not self._zoom_drag.active or self._zoom_drag.press_scene is None:
            return False
        cur = scene_pos
        if not self._zoom_drag.dragging:
            press = self._zoom_drag.press_scene
            d = abs(cur.x() - press.x()) + abs(cur.y() - press.y())
            if d > self._rc_drag_thresh_px:
                self._zoom_drag.dragging = True

        last_scene = self._zoom_drag.last_scene or cur
        dx_px = cur.x() - last_scene.x()
        dy_px = cur.y() - last_scene.y()
        s = self._rc_zoom_sensitivity
        sx = float(np.exp(-s * dx_px))
        sy = float(np.exp(+s * dy_px))
        sx = max(0.2, min(5.0, sx))
        sy = max(0.2, min(5.0, sy))
        if self._zoom_drag.pivot_view is not None:
            self.vb.scaleBy((sx, sy), center=self._zoom_drag.pivot_view)

        self._zoom_drag.last_scene = cur
        return True

    def _end_zoom_drag(self) -> None:
        """Reset the zoom drag state."""

        self._zoom_drag.reset()

    def _show_context_menu(self, ev) -> None:
        menu = QtWidgets.QMenu(self.plot)
        act_add = menu.addAction("Add Key Here")
        act_del = menu.addAction("Delete Nearest")
        chosen = menu.exec(ev.screenPos())
        if chosen is None:
            return

        if chosen is act_add:
            vp = self._scene_to_view(ev.scenePos())
            t, v = float(max(0.0, vp.x())), float(vp.y())
            kf = self._create_keyframe(t, v)
            if kf is not None:
                self.sel.set_single(self.provider.track_id, id(kf))
                self.on_changed()

        elif chosen is act_del:
            try:
                hit = self.sel.hit_test_nearest(ev.scenePos(), px_thresh=9999)
                if not hit:
                    return
                key = self._resolve_key(hit)
                if not key:
                    return
                self._key_drag.reset()
                self.sel.discard(hit.track_id, hit.key_id)
                if self.delete_key_cb:
                    self.delete_key_cb(key)
                else:
                    # フォールバック（Undoなし直書き）
                    track = self._track_for_id(hit.track_id)
                    if track and key in track.keys:
                        track.keys.remove(key)
                self.on_changed()
                return
            except Exception:
                logger.exception("Failed to delete keyframe from context menu")
                return

    def _create_keyframe(self, t: float, v: float) -> Optional[Keyframe]:
        """Create a keyframe via callback or a fallback implementation."""

        if self.add_key_cb:
            return self.add_key_cb(t, v)
        kf = Keyframe(t, v)
        track = self._track_for_id(str(self.provider.track_id))
        if track is None:
            return None
        track.keys.append(kf)
        track.clamp_times()
        return kf
