from __future__ import annotations

from dataclasses import dataclass
from typing import List

from .timeline import Timeline, Keyframe


@dataclass
class _TimelineSnapshot:
    duration_s: float
    track_name: str
    track_interp: str
    keys: List[Keyframe]


def _clone_keyframes(keys: List[Keyframe]) -> List[Keyframe]:
    return [Keyframe(k.t, k.v) for k in keys]


def _snapshot_from_timeline(timeline: Timeline) -> _TimelineSnapshot:
    track = timeline.track
    return _TimelineSnapshot(
        duration_s=timeline.duration_s,
        track_name=track.name,
        track_interp=track.interp.value,
        keys=_clone_keyframes(track.keys),
    )


def _apply_snapshot(dest: Timeline, snap: _TimelineSnapshot) -> None:
    dest.duration_s = float(snap.duration_s)
    track = dest.track
    track.name = snap.track_name
    track.interp = track.interp.__class__(snap.track_interp)
    track.keys = _clone_keyframes(snap.keys)


class TimelineHistory:
    """A simple undo/redo stack for :class:`Timeline` objects."""

    def __init__(self, timeline: Timeline, limit: int = 200):
        self._timeline = timeline
        self._limit = max(2, int(limit))
        self._states: List[_TimelineSnapshot] = [_snapshot_from_timeline(timeline)]
        self._index = 0

    # ---- push ----
    def push(self) -> None:
        """Capture the current timeline state as a new undo step."""
        snap = _snapshot_from_timeline(self._timeline)
        # discard redo states
        if self._index + 1 < len(self._states):
            self._states = self._states[: self._index + 1]
        self._states.append(snap)
        self._index += 1
        # trim oldest states if above limit
        if len(self._states) > self._limit:
            drop = len(self._states) - self._limit
            self._states = self._states[drop:]
            self._index = max(0, self._index - drop)

    # ---- queries ----
    def can_undo(self) -> bool:
        return self._index > 0

    def can_redo(self) -> bool:
        return self._index + 1 < len(self._states)

    # ---- operations ----
    def undo(self) -> bool:
        if not self.can_undo():
            return False
        self._index -= 1
        _apply_snapshot(self._timeline, self._states[self._index])
        return True

    def redo(self) -> bool:
        if not self.can_redo():
            return False
        self._index += 1
        _apply_snapshot(self._timeline, self._states[self._index])
        return True
