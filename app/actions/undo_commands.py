# actions/undo_commands.py
from __future__ import annotations
from dataclasses import replace
from typing import List, Optional, Sequence, Tuple
from PySide6.QtGui import QUndoCommand
from ..core.timeline import Timeline, Keyframe, Track, Handle


def _find_track(tl: Timeline, track_id: str) -> Optional[Track]:
    for tr in tl.iter_tracks():
        if tr.track_id == track_id:
            return tr
    return None


class _ClampMixin:
    def _clamp(self, track: Track):
        track.clamp_times()


class AddKeyCommand(QUndoCommand, _ClampMixin):
    def __init__(
        self,
        tl: Timeline,
        track_id: str,
        t: float,
        v: float,
        *,
        handle_in: Handle | Sequence[float] | Tuple[float, float] | None = None,
        handle_out: Handle | Sequence[float] | Tuple[float, float] | None = None,
        label: str = "Add Key",
        parent: Optional[QUndoCommand] = None,
    ):
        super().__init__(label, parent)
        self.tl = tl
        self.track_id = str(track_id)
        self.k: Keyframe | None = None
        self.t, self.v = float(t), float(v)
        self._handle_in = handle_in
        self._handle_out = handle_out

    def _clone_handle_data(self, data, *, fallback_t: float, fallback_v: float) -> Handle:
        if data is None:
            return Handle(fallback_t, fallback_v)
        if isinstance(data, Handle):
            return replace(data)
        if isinstance(data, (list, tuple)) and len(data) == 2:
            return Handle(float(data[0]), float(data[1]))
        if isinstance(data, dict):
            return Handle.from_mapping(data, default_t=fallback_t, default_v=fallback_v)
        return Handle(fallback_t, fallback_v)

    def redo(self):
        track = _find_track(self.tl, self.track_id)
        if track is None:
            return
        if self.k is None:
            handle_in = self._clone_handle_data(
                self._handle_in, fallback_t=self.t, fallback_v=self.v
            )
            handle_out = self._clone_handle_data(
                self._handle_out, fallback_t=self.t, fallback_v=self.v
            )
            self.k = Keyframe(self.t, self.v, handle_in=handle_in, handle_out=handle_out)
        if self.k not in track.keys:
            track.keys.append(self.k)
            self._clamp(track)

    def undo(self):
        track = _find_track(self.tl, self.track_id)
        if track is None or self.k is None:
            return
        if self.k in track.keys:
            track.keys.remove(self.k)


class DeleteKeysCommand(QUndoCommand, _ClampMixin):
    def __init__(self, tl: Timeline, track_id: str, targets: Sequence[Keyframe],
                 label: str = "Delete Keys", parent: Optional[QUndoCommand] = None):
        super().__init__(label, parent)
        self.tl = tl
        self.track_id = str(track_id)
        track = _find_track(tl, self.track_id)
        keys = track.keys if track is not None else []
        idx_map = {id(k): i for i, k in enumerate(keys)}
        items = []
        for k in targets:
            if id(k) in idx_map:
                items.append((idx_map[id(k)], k))
        self._items: List[Tuple[int, Keyframe]] = sorted(
            items, key=lambda x: x[0]
        )

    def redo(self):
        track = _find_track(self.tl, self.track_id)
        if track is None:
            return
        keys = track.keys
        for _, k in reversed(self._items):
            if k in keys:
                keys.remove(k)

    def undo(self):
        track = _find_track(self.tl, self.track_id)
        if track is None:
            return
        keys = track.keys
        for i, k in self._items:
            if k not in keys:
                keys.insert(min(i, len(keys)), k)
        self._clamp(track)


class MoveKeyCommand(QUndoCommand, _ClampMixin):
    def __init__(self, tl: Timeline, track_id: str, key: Keyframe,
                 before: Tuple[float, float], after: Tuple[float, float],
                 label: str = "Move Key", parent: Optional[QUndoCommand] = None):
        super().__init__(label, parent)
        self.tl = tl
        self.track_id = str(track_id)
        self.key = key
        self.bt, self.bv = before
        self.at, self.av = after

    def _apply(self, t, v):
        new_t = float(max(0.0, t))
        new_v = float(v)
        dt = new_t - self.key.t
        dv = new_v - self.key.v
        self.key.translate(dt, dv)
        track = _find_track(self.tl, self.track_id)
        if track is not None:
            self._clamp(track)

    def redo(self):
        self._apply(self.at, self.av)

    def undo(self):
        self._apply(self.bt, self.bv)


class SetKeyTimeCommand(QUndoCommand, _ClampMixin):
    def __init__(self, tl: Timeline, track_id: str, key: Keyframe,
                 old_t: float, new_t: float, label: str = "Set Time",
                 parent: Optional[QUndoCommand] = None):
        super().__init__(label, parent)
        self.tl = tl
        self.track_id = str(track_id)
        self.key = key
        self.old_t = float(old_t)
        self.new_t = float(new_t)

    def redo(self):
        self.key.set_time(max(0.0, self.new_t))
        track = _find_track(self.tl, self.track_id)
        if track is not None:
            self._clamp(track)

    def undo(self):
        self.key.set_time(max(0.0, self.old_t))
        track = _find_track(self.tl, self.track_id)
        if track is not None:
            self._clamp(track)


class SetKeyValueCommand(QUndoCommand):
    def __init__(self, key: Keyframe, old_v: float, new_v: float, label: str = "Set Value",
                 parent: Optional[QUndoCommand] = None):
        super().__init__(label, parent)
        self.key = key
        self.old_v = float(old_v)
        self.new_v = float(new_v)

    def redo(self):
        self.key.set_value(self.new_v)

    def undo(self):
        self.key.set_value(self.old_v)


class AddTrackCommand(QUndoCommand):
    def __init__(self, tl: Timeline, track: Optional[Track] = None, *, index: Optional[int] = None,
                 label: str = "Add Track", parent: Optional[QUndoCommand] = None):
        super().__init__(label, parent)
        self.tl = tl
        self.track = track or Track()
        self._index = index

    def redo(self):
        if self.track in self.tl.tracks:
            return
        if self._index is None or self._index >= len(self.tl.tracks):
            self.tl.tracks.append(self.track)
            self._index = self.tl.tracks.index(self.track)
        else:
            self.tl.tracks.insert(self._index, self.track)

    def undo(self):
        if self.track in self.tl.tracks:
            self.tl.tracks.remove(self.track)


class RenameTrackCommand(QUndoCommand):
    def __init__(
        self,
        tl: Timeline,
        track_id: str,
        new_name: str,
        *,
        old_name: Optional[str] = None,
        label: str = "Rename Track",
        parent: Optional[QUndoCommand] = None,
    ) -> None:
        super().__init__(label, parent)
        self.tl = tl
        self.track_id = str(track_id)
        self.new_name = str(new_name)
        track = _find_track(tl, self.track_id)
        if old_name is not None:
            self.old_name = str(old_name)
        else:
            self.old_name = track.name if track is not None else self.new_name

    def redo(self):
        track = _find_track(self.tl, self.track_id)
        if track is None:
            return
        track.name = self.new_name

    def undo(self):
        track = _find_track(self.tl, self.track_id)
        if track is None:
            return
        track.name = self.old_name


class RemoveTrackCommand(QUndoCommand):
    def __init__(self, tl: Timeline, track_id: str, label: str = "Remove Track",
                 parent: Optional[QUndoCommand] = None):
        super().__init__(label, parent)
        self.tl = tl
        self.track_id = str(track_id)
        self._removed: Optional[Track] = None
        self._index: Optional[int] = None

    def redo(self):
        if len(self.tl.tracks) <= 1:
            return
        for idx, track in enumerate(list(self.tl.tracks)):
            if track.track_id == self.track_id:
                self._removed = track
                self._index = idx
                del self.tl.tracks[idx]
                break

    def undo(self):
        if self._removed is None or self._index is None:
            return
        if self._removed in self.tl.tracks:
            return
        idx = min(self._index, len(self.tl.tracks))
        self.tl.tracks.insert(idx, self._removed)
