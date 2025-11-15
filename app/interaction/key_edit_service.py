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
from ..core.timeline import Handle, Keyframe, Timeline, Track, initialize_handle_positions
from .selection import KeyPoint, KeyPosProvider, SelectedKey, SelectionManager


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
                self._drag.start_tv = (handle.t, handle.v)
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
            key.translate(new_t - key.t, new_v - key.v)
            track = self._track_for_id(key_point.track_id)
            if track is not None:
                track.clamp_times()
        else:
            handle = self._resolve_handle(key_point)
            if handle is None:
                return False
            handle.t = float(new_t)
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
                t1, v1 = handle.t, handle.v
                if abs(t0 - t1) > 1e-12 or abs(v0 - v1) > 1e-12:
                    attr = "handle_in" if key_point.component == "handle_in" else "handle_out"
                    cmd = MoveHandleCommand(
                        self.timeline,
                        key_point.track_id,
                        key,
                        attr,
                        (t0, v0),
                        (t1, v1),
                    )
                    try:
                        self._push_undo(cmd)
                    except Exception:  # pragma: no cover - defensive
                        logger.exception("Failed to push MoveHandleCommand to undo stack")

        self._drag.reset()
        return True

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
        if kp.component == "handle_in":
            return getattr(key, "handle_in", None)
        if kp.component == "handle_out":
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

