"""Keyframe editing service coordinating undo-aware operations."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable, Optional

from PySide6.QtCore import QPointF
from PySide6.QtGui import QUndoCommand

from ..actions.undo_commands import (
    AddKeyCommand,
    DeleteKeysCommand,
    MoveHandleCommand,
    MoveKeyCommand,
)
from ..core.timeline import Handle, Keyframe, Timeline, Track, TrackType, initialize_handle_positions
from .selection import KeyPoint, KeyPosProvider, SelectedKey, SelectionManager
from .clipboard import copy_keyframe, get_clipboard


logger = logging.getLogger(__name__)


UndoPusher = Callable[[QUndoCommand], None]
SceneToView = Callable[[QPointF], QPointF]


@dataclass
class _DragState:
    key_point: Optional[KeyPoint] = None
    start_tv: tuple[float, float] | None = None

    @property
    def active(self) -> bool:
        return self.key_point is not None

    def reset(self) -> None:
        self.key_point = None
        self.start_tv = None


class KeyEditService:
    """Owns keyframe add/move/delete operations with undo integration."""

    def __init__(
        self,
        timeline: Timeline,
        selection: SelectionManager,
        pos_provider: KeyPosProvider,
        *,
        push_undo: Optional[UndoPusher] = None,
    ) -> None:
        self.timeline = timeline
        self.selection = selection
        self.provider = pos_provider
        self._push_undo = push_undo
        self._drag = _DragState()

    # ------------------------------------------------------------------
    # Drag lifecycle
    # ------------------------------------------------------------------
    def begin_drag(self, hit: KeyPoint) -> None:
        """Begin dragging ``hit`` and cache its initial coordinates."""

        self._drag.key_point = hit
        key = self._resolve_key(hit)
        if key is None:
            self._drag.start_tv = None
            return
        if hit.component == "key":
            self._drag.start_tv = (key.t, key.v)
        else:
            handle = self._resolve_handle(hit)
            if handle is not None:
                # Vector2Trackの場合、component名からX/Yを判定
                if hit.component.endswith("_x"):
                    handle_v = handle.vx if handle.vx is not None else handle.v
                elif hit.component.endswith("_y"):
                    handle_v = handle.vy if handle.vy is not None else handle.v
                else:
                    handle_v = handle.v
                self._drag.start_tv = (handle.t, handle_v)
            else:
                self._drag.start_tv = None

    def update_drag(self, scene_pos: QPointF, scene_to_view: SceneToView) -> bool:
        """Update the active drag to ``scene_pos``."""

        if not self._drag.active:
            return False
        key_point = self._drag.key_point
        if key_point is None:
            return False
        key = self._resolve_key(key_point)
        if key is None:
            return False

        mp = scene_to_view(scene_pos)
        new_t = float(mp.x())
        new_v = float(mp.y())

        if key_point.component == "key":
            new_t = float(max(0.0, new_t))
            track = self._track_for_id(key_point.track_id)
            is_vector2 = track is not None and getattr(track, "track_type", TrackType.SCALAR) == TrackType.VECTOR2
            if is_vector2:
                # Vector2Trackの場合、時間軸のみを変更（値は変更しない）
                key.set_time(new_t)
            else:
                # ScalarTrackの場合、従来通り
                key.translate(new_t - key.t, new_v - key.v)
            if track is not None:
                track.clamp_times()
        else:
            handle = self._resolve_handle(key_point)
            if handle is None:
                return False
            
            # 時間軸は同期して更新（表示オフセットは表示のみに影響し、実際の値には影響しない）
            handle.t = float(new_t)
            # Vector2Trackの場合、component名からX/Yを判定して値を更新
            if key_point.component.endswith("_x"):
                handle.vx = float(new_v)
            elif key_point.component.endswith("_y"):
                handle.vy = float(new_v)
            else:
                handle.v = float(new_v)
        return True

    def commit_drag(self) -> bool:
        """Finish the drag, pushing an undo command when appropriate."""

        if not self._drag.active:
            return False

        key_point = self._drag.key_point
        key = self._resolve_key(key_point) if key_point is not None else None
        if key_point is None or key is None:
            self._drag.reset()
            return False

        if self._drag.start_tv is None or self._push_undo is None:
            self._drag.reset()
            return True

        t0, v0 = self._drag.start_tv
        if key_point.component == "key":
            t1, v1 = key.t, key.v
            if abs(t0 - t1) > 1e-12 or abs(v0 - v1) > 1e-12:
                cmd = MoveKeyCommand(
                    self.timeline, key_point.track_id, key, (t0, v0), (t1, v1)
                )
                try:
                    self._push_undo(cmd)
                except Exception:  # pragma: no cover - defensive
                    logger.exception("Failed to push MoveKeyCommand to undo stack")
        else:
            handle = self._resolve_handle(key_point)
            if handle is not None:
                # Vector2Trackの場合、component名からX/Yを判定
                if key_point.component.endswith("_x"):
                    v1 = handle.vx if handle.vx is not None else handle.v
                    component_suffix = "_x"
                elif key_point.component.endswith("_y"):
                    v1 = handle.vy if handle.vy is not None else handle.v
                    component_suffix = "_y"
                else:
                    v1 = handle.v
                    component_suffix = ""
                t1 = handle.t
                if abs(t0 - t1) > 1e-12 or abs(v0 - v1) > 1e-12:
                    # component名からベース名を取得（"_x"や"_y"を除去）
                    base_component = key_point.component
                    if component_suffix:
                        base_component = base_component[:-len(component_suffix)]
                    attr = "handle_in" if base_component == "handle_in" else "handle_out"
                    cmd = MoveHandleCommand(
                        self.timeline,
                        key_point.track_id,
                        key,
                        attr,
                        (t0, v0),
                        (t1, v1),
                        component=component_suffix[1:] if component_suffix else None,
                    )
                    try:
                        self._push_undo(cmd)
                    except Exception:  # pragma: no cover - defensive
                        logger.exception("Failed to push MoveHandleCommand to undo stack")

        self._drag.reset()
        return True

    # ------------------------------------------------------------------
    # Copy / paste / delete selected
    # ------------------------------------------------------------------
    def copy_selected_keys(self) -> bool:
        """Copy selected keyframe values to clipboard."""
        selected = self.selection.selected
        if not selected:
            return False
        
        # 最初に選択されたキー（キーフレームのみ）をコピー
        key_selected = [sel for sel in selected if sel.component == "key"]
        if not key_selected:
            return False
        
        sel = key_selected[0]
        key = self._resolve_key(sel)
        if key is None:
            return False
        
        track = self._track_for_id(sel.track_id)
        if track is None:
            return False
        
        track_type = getattr(track, "track_type", TrackType.SCALAR)
        copy_keyframe(key, track_type)
        return True

    def paste_at(self, time: float) -> Optional[Keyframe]:
        """Paste clipboard value at specified time."""
        clipboard = get_clipboard()
        if clipboard is None:
            return None
        
        track_id = self._active_track_id()
        if track_id is None:
            return None
        
        track = self._track_for_id(track_id)
        if track is None:
            return None
        
        track_type = getattr(track, "track_type", TrackType.SCALAR)
        v, vx, vy = clipboard.to_keyframe_value()
        
        # トラックタイプが一致する場合のみペースト
        if track_type != clipboard.track_type:
            return None
        
        if track_type == TrackType.VECTOR2:
            # Vector2Trackの場合
            if vx is None or vy is None:
                return None
            key = self.add_at(time, v)
            if key is not None:
                key.set_value_x(vx)
                key.set_value_y(vy)
        else:
            # ScalarTrackの場合
            key = self.add_at(time, v)
        
        return key

    def delete_selected_keys(self) -> bool:
        """Delete all selected keyframes."""
        selected = self.selection.selected
        if not selected:
            return False
        
        # キーフレームのみを削除対象とする
        key_selected = [sel for sel in selected if sel.component == "key"]
        if not key_selected:
            return False
        
        # トラックごとにグループ化
        keys_by_track: dict[str, list[Keyframe]] = {}
        for sel in key_selected:
            key = self._resolve_key(sel)
            if key is None:
                continue
            track_id = sel.track_id
            if track_id not in keys_by_track:
                keys_by_track[track_id] = []
            keys_by_track[track_id].append(key)
        
        # 各トラックのキーを削除
        deleted = False
        for track_id, keys in keys_by_track.items():
            if not keys:
                continue
            
            # 選択から削除
            for sel in key_selected:
                if sel.track_id == track_id:
                    self.selection.discard(sel.track_id, sel.key_id)
            
            # Undoコマンドで削除
            if self._push_undo is not None:
                cmd = DeleteKeysCommand(self.timeline, track_id, keys)
                try:
                    self._push_undo(cmd)
                    deleted = True
                except Exception:  # pragma: no cover - defensive
                    logger.exception("Failed to push DeleteKeysCommand to undo stack")
            else:
                # Fallback: 直接削除
                track = self._track_for_id(track_id)
                if track is not None:
                    for key in keys:
                        if key in track.keys:
                            track.keys.remove(key)
                    deleted = True
        
        return deleted

    # ------------------------------------------------------------------
    # Add / delete helpers
    # ------------------------------------------------------------------
    def add_at(self, time: float, value: float) -> Optional[Keyframe]:
        """Add a keyframe at ``time``/``value`` and select it."""

        track_id = self._active_track_id()
        key: Optional[Keyframe] = None

        if self._push_undo is not None and track_id is not None:
            cmd = AddKeyCommand(self.timeline, track_id, time, value)
            try:
                self._push_undo(cmd)
            except Exception:  # pragma: no cover - defensive
                logger.exception("Failed to push AddKeyCommand to undo stack")
            key = cmd.k
        else:
            key = self._create_keyframe_fallback(time, value, track_id)

        if key is not None and track_id is not None:
            self.selection.set_single(track_id, id(key))
        return key

    def delete_at(self, scene_pos: QPointF, *, px_thresh: int = 10) -> bool:
        """Delete the nearest keyframe to ``scene_pos`` if within ``px_thresh``."""

        hit = self.selection.hit_test_nearest(scene_pos, px_thresh=px_thresh)
        if not hit:
            return False
        if hit is None or hit.component != "key":
            return False

        key = self._resolve_key(hit)
        if key is None:
            return False

        self._drag.reset()
        self.selection.discard(hit.track_id, hit.key_id)

        if self._push_undo is not None:
            cmd = DeleteKeysCommand(self.timeline, hit.track_id, [key])
            try:
                self._push_undo(cmd)
            except Exception:  # pragma: no cover - defensive
                logger.exception("Failed to push DeleteKeysCommand to undo stack")
        else:
            track = self._track_for_id(hit.track_id)
            if track is not None and key in track.keys:
                track.keys.remove(key)

        return True

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _active_track_id(self) -> Optional[str]:
        track_id = getattr(self.provider, "track_id", None)
        if track_id is None:
            return None
        return str(track_id)

    def _track_for_id(self, track_id: str) -> Optional[Track]:
        for track in self.timeline.iter_tracks():
            if track.track_id == track_id:
                return track
        return None

    def _resolve_key(self, kp: KeyPoint | None) -> Optional[Keyframe]:
        if kp is None:
            return None
        track = self._track_for_id(kp.track_id)
        if track is None:
            return None
        for key in track.keys:
            if id(key) == kp.key_id:
                return key
        return None

    def _resolve_handle(self, kp: KeyPoint | SelectedKey | None):
        if kp is None:
            return None
        key = self._resolve_key(kp)
        if key is None:
            return None
        # component名からベース名を取得（"_x"や"_y"を除去）
        base_component = kp.component
        if base_component.endswith("_x") or base_component.endswith("_y"):
            base_component = base_component[:-2]
        if base_component == "handle_in":
            return getattr(key, "handle_in", None)
        if base_component == "handle_out":
            return getattr(key, "handle_out", None)
        return None

    def _create_keyframe_fallback(
        self, time: float, value: float, track_id: Optional[str]
    ) -> Optional[Keyframe]:
        if track_id is None:
            return None
        track = self._track_for_id(track_id)
        if track is None:
            return None
        t = float(time)
        v = float(value)
        key = Keyframe(
            t,
            v,
            handle_in=Handle(t, v),
            handle_out=Handle(t, v),
        )
        track.keys.append(key)
        track.clamp_times()
        initialize_handle_positions(track, key)
        return key

