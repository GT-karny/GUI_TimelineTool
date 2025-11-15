# interaction/selection.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Iterable, Optional, Protocol, Set
from PySide6 import QtWidgets
from PySide6.QtCore import QPointF, QRectF
import pyqtgraph as pg


# ---- 軽量キー表現（描画/ヒットテスト用の最小情報）----
@dataclass(frozen=True)
class KeyPoint:
    track_id: str
    key_id: int       # owner key id
    t: float
    v: float
    component: str = "key"
    item_id: int | None = None

    def __post_init__(self) -> None:
        if self.item_id is None:
            object.__setattr__(self, "item_id", int(self.key_id))

    def to_selected(self) -> "SelectedKey":
        return SelectedKey(self.track_id, self.key_id, self.component, self.item_id)


@dataclass(frozen=True)
class SelectedKey:
    """選択されたキー/ハンドルを識別する構造体。"""

    track_id: str
    key_id: int
    component: str = "key"
    item_id: int | None = None

    def __post_init__(self) -> None:
        if self.item_id is None:
            object.__setattr__(self, "item_id", int(self.key_id))

    @property
    def is_key(self) -> bool:
        return self.component == "key"


# ---- 座標提供インタフェース（トラック種類を知らないため）----
class KeyPosProvider(Protocol):
    def iter_all_keypoints(self) -> Iterable[KeyPoint]:
        """現在描画すべきすべてのキー点を返す。"""

    def scene_pos_of(self, kp: KeyPoint) -> QPointF:
        """KeyPoint のシーン座標（QGraphicsScene座標系）を返す。"""


class SelectionManager:
    """
    選択集合とヒットテスト/マルキー確定のみ担当。
    - 選択は (track_id, key_id) のセットで管理
    - ヒットテストは KeyPosProvider に委譲（トラック種類に非依存）
    - 見た目の強調は呼び出し側（レンダラ/TimelinePlot）に任せる
    """

    def __init__(self, scene: QtWidgets.QGraphicsScene, provider: KeyPosProvider):
        self._scene = scene
        self._provider = provider

        self.selected: Set[SelectedKey] = set()
        self._marquee_rect_item: Optional[QtWidgets.QGraphicsRectItem] = None
        self._marquee_active = False
        self._marquee_start_scene: Optional[QPointF] = None

    # ---- 基本操作 ----
    def clear(self) -> None:
        self.selected.clear()

    def _make_selected(
        self,
        track_id: str,
        key_id: int,
        *,
        component: str = "key",
        item_id: int | None = None,
    ) -> SelectedKey:
        track_id = str(track_id)
        key_id = int(key_id)
        if item_id is None:
            item_id = key_id
        else:
            item_id = int(item_id)
        return SelectedKey(track_id, key_id, component, item_id)

    def set_single(
        self,
        track_id: str,
        key_id: int,
        *,
        component: str = "key",
        item_id: int | None = None,
    ) -> None:
        self.selected = {self._make_selected(track_id, key_id, component=component, item_id=item_id)}

    def set_single_point(self, point: KeyPoint) -> None:
        self.selected = {point.to_selected()}

    def add(
        self,
        track_id: str,
        key_id: int,
        *,
        component: str = "key",
        item_id: int | None = None,
    ) -> None:
        self.selected.add(self._make_selected(track_id, key_id, component=component, item_id=item_id))

    def add_point(self, point: KeyPoint) -> None:
        self.selected.add(point.to_selected())

    def discard(
        self,
        track_id: str,
        key_id: int,
        *,
        component: str = "key",
        item_id: int | None = None,
    ) -> None:
        self.selected.discard(self._make_selected(track_id, key_id, component=component, item_id=item_id))

    def discard_point(self, point: KeyPoint) -> None:
        self.discard(point.track_id, point.key_id, component=point.component, item_id=point.item_id)

    def toggle(
        self,
        track_id: str,
        key_id: int,
        *,
        component: str = "key",
        item_id: int | None = None,
    ) -> None:
        sel = self._make_selected(track_id, key_id, component=component, item_id=item_id)
        if sel in self.selected:
            self.selected.remove(sel)
        else:
            self.selected.add(sel)

    def toggle_point(self, point: KeyPoint) -> None:
        self.toggle(point.track_id, point.key_id, component=point.component, item_id=point.item_id)

    def retain_tracks(self, valid_track_ids: Iterable[str]) -> None:
        """存在しないトラックに紐づく選択を破棄する。"""

        valid = {str(tid) for tid in valid_track_ids}
        self.selected = {sel for sel in self.selected if sel.track_id in valid}

    def set_scene(self, scene: QtWidgets.QGraphicsScene) -> None:
        if self._scene is scene:
            return
        if self._marquee_rect_item is not None:
            try:
                self._scene.removeItem(self._marquee_rect_item)
            except Exception:
                pass
            self._marquee_rect_item = None
        self._marquee_active = False
        self._marquee_start_scene = None
        self._scene = scene

    def grouped_by_track(self) -> Dict[str, Set[int]]:
        """track_id -> {key_id} の辞書を返す。"""

        grouped: Dict[str, Set[int]] = {}
        for sel in self.selected:
            if not sel.is_key:
                continue
            grouped.setdefault(sel.track_id, set()).add(sel.key_id)
        return grouped

    # ---- ヒットテスト（最短距離・ピクセル閾値）----
    def hit_test_nearest(self, scene_pos: QPointF, px_thresh: int = 10) -> Optional[KeyPoint]:
        best: Optional[KeyPoint] = None
        best_d = 1e9
        for kp in self._provider.iter_all_keypoints():
            sp = self._provider.scene_pos_of(kp)
            # Robust Manhattan distance for QPointF (avoid QPointF.manhattanLength)
            d = abs(sp.x() - scene_pos.x()) + abs(sp.y() - scene_pos.y())
            if d < best_d:
                best_d = d
                best = kp
        if best is not None and best_d <= px_thresh:
            return best
        return None

    # ---- マルキー（矩形選択）----
    def marquee_begin(self, scene_pos: QPointF) -> None:
        if self._marquee_active:
            return
        self._marquee_active = True
        self._marquee_start_scene = scene_pos
        rect = QtWidgets.QGraphicsRectItem()
        rect.setPen(pg.mkPen(0, 120, 255, 180, width=1))
        rect.setBrush(pg.mkBrush(0, 120, 255, 40))
        self._scene.addItem(rect)
        self._marquee_rect_item = rect

    def marquee_update(self, scene_pos: QPointF) -> None:
        if not self._marquee_active or not self._marquee_rect_item or self._marquee_start_scene is None:
            return
        r = QRectF(self._marquee_start_scene, scene_pos).normalized()
        self._marquee_rect_item.setRect(r)

    def marquee_commit(self, additive: bool = False) -> None:
        if not (self._marquee_active and self._marquee_rect_item):
            return
        rect = self._marquee_rect_item.rect()

        newly: Set[SelectedKey] = set()
        for kp in self._provider.iter_all_keypoints():
            if kp.component != "key":
                continue
            sp = self._provider.scene_pos_of(kp)
            if rect.contains(sp):
                newly.add(kp.to_selected())

        if additive:
            self.selected |= newly
        else:
            self.selected = newly

        # cleanup
        self._scene.removeItem(self._marquee_rect_item)
        self._marquee_rect_item = None
        self._marquee_active = False
        self._marquee_start_scene = None
