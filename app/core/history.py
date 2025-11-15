from __future__ import annotations

from dataclasses import dataclass
from typing import List

from .timeline import Timeline, Keyframe, Track, InterpMode


@dataclass
class _TimelineSnapshot:
    duration_s: float
    tracks: List["_TrackSnapshot"]


@dataclass
class _TrackSnapshot:
    track_id: str
    name: str
    interp: str
    keys: List[Keyframe]


def _clone_keyframes(keys: List[Keyframe]) -> List[Keyframe]:
    cloned: List[Keyframe] = []
    for k in keys:
        cloned.append(
            Keyframe(
                k.t,
                k.v,
                handle_in=k.handle_in.copy() if k.handle_in is not None else None,
                handle_out=k.handle_out.copy() if k.handle_out is not None else None,
            )
        )
    return cloned


def _snapshot_from_timeline(timeline: Timeline) -> _TimelineSnapshot:
    return _TimelineSnapshot(
        duration_s=timeline.duration_s,
        tracks=[
            _TrackSnapshot(
                track_id=track.track_id,
                name=track.name,
                interp=track.interp.value,
                keys=_clone_keyframes(track.keys),
            )
            for track in timeline.tracks
        ],
    )


def _apply_snapshot(dest: Timeline, snap: _TimelineSnapshot) -> None:
    dest.duration_s = float(snap.duration_s)
    id_to_track = {track.track_id: track for track in dest.tracks}
    dest.tracks = []
    for track_snap in snap.tracks:
        source = id_to_track.get(track_snap.track_id)
        if source is None:
            source = Track(
                name=track_snap.name,
                interp=InterpMode(track_snap.interp),
                keys=_clone_keyframes(track_snap.keys),
                track_id=track_snap.track_id,
            )
        else:
            source.name = track_snap.name
            source.interp = InterpMode(track_snap.interp)
            source.keys = _clone_keyframes(track_snap.keys)
        dest.tracks.append(source)
    if not dest.tracks:
        dest.tracks = [Track()]


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
