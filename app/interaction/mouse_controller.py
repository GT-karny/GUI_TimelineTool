# interaction/mouse_controller.py
from __future__ import annotations
from typing import Optional, Callable
import numpy as np
from PySide6 import QtCore, QtWidgets
from PySide6.QtCore import QPointF
import pyqtgraph as pg

from ..core.timeline import Timeline, Keyframe
from ..core.interpolation import evaluate
from .selection import SelectionManager, KeyPoint, KeyPosProvider


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
        self._dragging_key: Optional[KeyPoint] = None

        # 中ボタンパン
        self._mid_panning = False
        self._mid_last_scene: Optional[QPointF] = None

        # 右ドラッグズーム
        self._rc_press_scene: Optional[QPointF] = None
        self._rc_last_scene: Optional[QPointF] = None
        self._rc_pivot_view: Optional[QPointF] = None
        self._rc_dragging = False
        self._rc_drag_thresh_px = 6
        self._rc_zoom_sensitivity = 0.002

        # イベントフック
        self.plot.scene().installEventFilter(self)

        self.commit_drag = commit_drag
        self.add_key_cb = add_key_cb          
        self.delete_key_cb = delete_key_cb    
        self._drag_start_tv: tuple[float, float] | None = None

    # ---- ショートカット ----
    @property
    def vb(self) -> pg.ViewBox:
        return self.plot.plotItem.vb

    def _scene_to_view(self, p: QPointF) -> QPointF:
        return self.vb.mapSceneToView(p)

    # ---- KeyPoint -> Keyframe 解決（単一トラック前提の簡易版）----
    def _resolve_key(self, kp: KeyPoint) -> Optional[Keyframe]:
        # 暫定：key_id は id(key) を想定。将来は安定IDに置換。
        for k in self.timeline.track.sorted():
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

        # ---------------- 左ボタン ----------------
        if et == QtCore.QEvent.GraphicsSceneMousePress and ev.button() == Qt.LeftButton:
            self._left_down = True
            hit = self.sel.hit_test_nearest(ev.scenePos(), px_thresh=10)
            if hit is not None:
                # 点上：その点を掴む（選択は単一に置き換え。Shiftで加算）
                if self._is_shift(ev):
                    self.sel.add(hit.track_id, hit.key_id)
                else:
                    self.sel.set_single(hit.track_id, hit.key_id)
                self._dragging_key = hit
                k = self._resolve_key(hit)
                if k is not None:
                    self._drag_start_tv = (k.t, k.v)
                self.on_changed()
            else:
                # 空白：選択が存在すれば解除、なければプレイヘッド移動
                if self.sel.selected:
                    self.sel.clear()
                    self.on_changed()
                else:
                    vp = self._scene_to_view(ev.scenePos())
                    self.set_playhead(max(0.0, float(vp.x())))
                # マルキー開始（常に開始しておく）
                self.sel.marquee_begin(ev.scenePos())
            return True

        if et == QtCore.QEvent.GraphicsSceneMouseMove and self._left_down:
            if self._dragging_key is not None:
                # ドラッグでキーを移動
                k = self._resolve_key(self._dragging_key)
                if k is not None:
                    mp = self._scene_to_view(ev.scenePos())
                    k.t = float(max(0.0, mp.x()))
                    k.v = float(mp.y())
                    self.timeline.track.clamp_times()
                    self.on_changed()
                return True
            # マルキー更新
            self.sel.marquee_update(ev.scenePos())
            self.on_changed()
            return True

        if et == QtCore.QEvent.GraphicsSceneMouseRelease and ev.button() == Qt.LeftButton:
            self._left_down = False
            if self._dragging_key is not None:
                k = self._resolve_key(self._dragging_key)
                if k is not None and self.commit_drag and self._drag_start_tv is not None:
                    t0, v0 = self._drag_start_tv
                    t1, v1 = k.t, k.v
                    if abs(t0 - t1) > 1e-12 or abs(v0 - v1) > 1e-12:
                        self.commit_drag(k, (t0, v0), (t1, v1))
                self._dragging_key = None
                self._drag_start_tv = None
            # Shift押下なら加算選択
            self.sel.marquee_commit(additive=self._is_shift(ev))
            self.on_changed()
            return True

        # 左ダブルクリック：カーソル位置にキー追加（スケール無関係）
        if et == QtCore.QEvent.GraphicsSceneMouseDoubleClick and ev.button() == Qt.LeftButton:
            vp = self._scene_to_view(ev.scenePos())
            t = float(max(0.0, vp.x()))
            v = float(vp.y())
            if self.add_key_cb:
                kf = self.add_key_cb(t, v)
                if kf is not None:
                    self.sel.set_single(0, id(kf))
                    self.on_changed()
            else:
                kf = Keyframe(t, v)
                self.timeline.track.keys.append(kf)
                self.timeline.track.clamp_times()
                self.sel.set_single(0, id(kf))
                self.on_changed()
            return True


        # ---------------- 中ボタン（パン） ----------------
        if et == QtCore.QEvent.GraphicsSceneMousePress and ev.button() == Qt.MiddleButton:
            self._mid_panning = True
            self._mid_last_scene = ev.scenePos()
            return True

        if et == QtCore.QEvent.GraphicsSceneMouseMove and self._mid_panning:
            if self._mid_last_scene is not None:
                v0 = self._scene_to_view(self._mid_last_scene)
                v1 = self._scene_to_view(ev.scenePos())
                self.vb.translateBy(x=-(v1.x() - v0.x()), y=-(v1.y() - v0.y()))
            self._mid_last_scene = ev.scenePos()
            return True

        if et == QtCore.QEvent.GraphicsSceneMouseRelease and ev.button() == Qt.MiddleButton:
            self._mid_panning = False
            self._mid_last_scene = None
            return True

        # ---------------- 右ボタン（ドラッグズーム / メニュー） ----------------
        if et == QtCore.QEvent.GraphicsSceneMousePress and ev.button() == Qt.RightButton:
            self._rc_press_scene = ev.scenePos()
            self._rc_last_scene = ev.scenePos()
            self._rc_pivot_view = self._scene_to_view(ev.scenePos())  # 押下位置を不動点に
            self._rc_dragging = False
            return True

        if et == QtCore.QEvent.GraphicsSceneMouseMove and (QtWidgets.QApplication.mouseButtons() & Qt.RightButton):
            if self._rc_press_scene is None:
                return True
            cur = ev.scenePos()
            if not self._rc_dragging:
                # Robust Manhattan distance for QPointF (avoid QPointF.manhattanLength)
                d = abs(cur.x() - self._rc_press_scene.x()) + abs(cur.y() - self._rc_press_scene.y())
                if d > self._rc_drag_thresh_px:
                    self._rc_dragging = True

            # ピボットを中心にXY独立スケール
            dx_px = cur.x() - (self._rc_last_scene.x() if self._rc_last_scene else cur.x())
            dy_px = cur.y() - (self._rc_last_scene.y() if self._rc_last_scene else cur.y())
            s = self._rc_zoom_sensitivity
            sx = float(np.exp(-s * dx_px))
            sy = float(np.exp(+s * dy_px))  # 画面座標は上が小さいので符号反転
            sx = max(0.2, min(5.0, sx))
            sy = max(0.2, min(5.0, sy))
            if self._rc_pivot_view is not None:
                self.vb.scaleBy((sx, sy), center=self._rc_pivot_view)

            self._rc_last_scene = cur
            return True

        if et == QtCore.QEvent.GraphicsSceneMouseRelease and ev.button() == Qt.RightButton:
            # ドラッグしてなければ簡易メニュー
            if not self._rc_dragging:
                self._show_context_menu(ev)
            # 後片付け
            self._rc_press_scene = None
            self._rc_last_scene = None
            self._rc_pivot_view = None
            self._rc_dragging = False
            return True

        # ---------------- ホイール（等倍率ズーム：任意） ----------------
        if et == QtCore.QEvent.GraphicsSceneWheel:
            # マウス位置を中心に X=Y 等倍率ズーム
            delta = ev.delta() if hasattr(ev, "delta") else ev.angleDelta().y()
            if delta:
                s = 0.9 if delta > 0 else 1.1
                center = self._scene_to_view(ev.scenePos())
                self.vb.scaleBy((s, s), center=center)
                return True

        return super().eventFilter(obj, ev)

    # ============================================================
    # Helpers
    # ============================================================
    def _is_shift(self, ev) -> bool:
        return bool(ev.modifiers() & QtCore.Qt.ShiftModifier)

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
            if self.add_key_cb:
                kf = self.add_key_cb(t, v)  # Undo経由で追加、Keyframe を返す想定
                if kf is not None:
                    self.sel.set_single(0, id(kf))
                    self.on_changed()
            else:
                # フォールバック（Undoなし直書き）
                kf = Keyframe(t, v)
                self.timeline.track.keys.append(kf)
                self.timeline.track.clamp_times()
                self.sel.set_single(0, id(kf))
                self.on_changed()

        elif chosen is act_del:
            try:
                hit = self.sel.hit_test_nearest(ev.scenePos(), px_thresh=9999)
                if not hit:
                    return
                key = self._resolve_key(hit)
                if not key:
                    return
                self._dragging_key = None
                self._drag_start_tv = None
                self.sel.discard(hit.track_id, hit.key_id)
                if self.delete_key_cb:
                    self.delete_key_cb(key)  
                else:
                    # フォールバック（Undoなし直書き）
                    if key in self.timeline.track.keys:
                        self.timeline.track.keys.remove(key)
                self.on_changed()
                return
            except Exception as e:
                import traceback
                print("[RC-DELETE ERROR]", e)
                traceback.print_exc()
                return
