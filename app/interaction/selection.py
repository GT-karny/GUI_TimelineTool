# interaction/selection.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable, Optional, Set, Protocol, Tuple
from PySide6 import QtWidgets
from PySide6.QtCore import QPointF, QRectF
import pyqtgraph as pg


# ---- 軽量キー表現（描画/ヒットテスト用の最小情報）----
@dataclass(frozen=True)
class KeyPoint:
    track_id: int
    key_id: int       # 安定ID推奨（暫定は id(key_obj) でも可）
    t: float
    v: float


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

        self.selected: Set[Tuple[int, int]] = set()  # {(track_id, key_id)}
        self._marquee_rect_item: Optional[QtWidgets.QGraphicsRectItem] = None
        self._marquee_active = False
        self._marquee_start_scene: Optional[QPointF] = None

    # ---- 基本操作 ----
    def clear(self) -> None:
        self.selected.clear()

    def set_single(self, track_id: int, key_id: int) -> None:
        self.selected = {(track_id, key_id)}

    def add(self, track_id: int, key_id: int) -> None:
        self.selected.add((track_id, key_id))

    def discard(self, track_id: int, key_id: int) -> None:
        self.selected.discard((track_id, key_id))

    def toggle(self, track_id: int, key_id: int) -> None:
        k = (track_id, key_id)
        if k in self.selected:
            self.selected.remove(k)
        else:
            self.selected.add(k)

    # ---- ヒットテスト（最短距離・ピクセル閾値）----
    def hit_test_nearest(self, scene_pos: QPointF, px_thresh: int = 10) -> Optional[KeyPoint]:
        best: Optional[KeyPoint] = None
        best_d = 1e9
        for kp in self._provider.iter_all_keypoints():
            sp = self._provider.scene_pos_of(kp)
            d = (sp - scene_pos).manhattanLength()
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

        newly: Set[Tuple[int, int]] = set()
        for kp in self._provider.iter_all_keypoints():
            sp = self._provider.scene_pos_of(kp)
            if rect.contains(sp):
                newly.add((kp.track_id, kp.key_id))

        if additive:
            self.selected |= newly
        else:
            self.selected = newly

        # cleanup
        self._scene.removeItem(self._marquee_rect_item)
        self._marquee_rect_item = None
        self._marquee_active = False
        self._marquee_start_scene = None
