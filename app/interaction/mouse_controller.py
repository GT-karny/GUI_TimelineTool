# interaction/mouse_controller.py
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional, Callable
import numpy as np
from PySide6 import QtCore, QtWidgets
from PySide6.QtCore import QPointF
import pyqtgraph as pg

from ..core.timeline import Timeline
from ..core.interpolation import evaluate
from .key_edit_service import KeyEditService
from .selection import SelectionManager, KeyPosProvider


logger = logging.getLogger(__name__)


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
        key_edit: KeyEditService,
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
        # 中ボタンパン
        self._mid_panning = False
        self._mid_last_scene: Optional[QPointF] = None

        # 右ドラッグズーム
        self._zoom_drag = ZoomDragState()
        self._rc_drag_thresh_px = 6
        self._rc_zoom_sensitivity = 0.002

        # イベントフック
        self.plot.scene().installEventFilter(self)

        self.key_edit = key_edit

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
            self.key_edit.begin_drag(hit)
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
        if self.key_edit.update_drag(ev.scenePos(), self._scene_to_view):
            self.on_changed()
            return True
        self.sel.marquee_update(ev.scenePos())
        self.on_changed()
        return True

    def _handle_left_button_release(self, ev: QtWidgets.QGraphicsSceneMouseEvent) -> bool:
        """Handle left button release by finalising drags or marquee."""

        self._left_down = False
        self.key_edit.commit_drag()
        self.sel.marquee_commit(additive=self._is_shift(ev))
        self.on_changed()
        return True

    def _handle_left_button_double_click(self, ev: QtWidgets.QGraphicsSceneMouseEvent) -> bool:
        """Handle double click by adding a key at the cursor position."""

        vp = self._scene_to_view(ev.scenePos())
        t = float(max(0.0, vp.x()))
        v = float(vp.y())
        if self.key_edit.add_at(t, v) is not None:
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
            if self.key_edit.add_at(t, v) is not None:
                self.on_changed()

        elif chosen is act_del:
            try:
                if self.key_edit.delete_at(ev.scenePos(), px_thresh=9999):
                    self.on_changed()
                return
            except Exception:
                logger.exception("Failed to delete keyframe from context menu")
                return
