# actions/undo_commands.py
from __future__ import annotations
from typing import List, Sequence, Tuple
from PySide6.QtGui import QUndoCommand
from ..core.timeline import Timeline, Keyframe


class _ClampMixin:
    def _clamp(self, tl: Timeline):
        tl.track.clamp_times()


class AddKeyCommand(QUndoCommand, _ClampMixin):
    def __init__(self, tl: Timeline, t: float, v: float, label: str = "Add Key"):
        super().__init__(label)
        self.tl = tl
        self.k: Keyframe | None = None
        self.t, self.v = float(t), float(v)

    def redo(self):
        if self.k is None:
            self.k = Keyframe(self.t, self.v)
        if self.k not in self.tl.track.keys:
            self.tl.track.keys.append(self.k)
            self._clamp(self.tl)

    def undo(self):
        if self.k in self.tl.track.keys:
            self.tl.track.keys.remove(self.k)


class DeleteKeysCommand(QUndoCommand, _ClampMixin):
    def __init__(self, tl: Timeline, targets: Sequence[Keyframe], label: str = "Delete Keys"):
        super().__init__(label)
        self.tl = tl
        keys = tl.track.keys
        idx_map = {id(k): i for i, k in enumerate(keys)}
        items = []
        for k in targets:
            if id(k) in idx_map:
                items.append((idx_map[id(k)], k))
        self._items: List[Tuple[int, Keyframe]] = sorted(
            items, key=lambda x: x[0]
        )

    def redo(self):
        keys = self.tl.track.keys
        for _, k in reversed(self._items):
            if k in keys:
                keys.remove(k)

    def undo(self):
        keys = self.tl.track.keys
        for i, k in self._items:
            if k not in keys:
                keys.insert(min(i, len(keys)), k)
        self._clamp(self.tl)


class MoveKeyCommand(QUndoCommand, _ClampMixin):
    def __init__(self, tl: Timeline, key: Keyframe, before: Tuple[float, float], after: Tuple[float, float],
                 label: str = "Move Key"):
        super().__init__(label)
        self.tl = tl
        self.key = key
        self.bt, self.bv = before
        self.at, self.av = after

    def _apply(self, t, v):
        self.key.t = float(max(0.0, t))
        self.key.v = float(v)
        self._clamp(self.tl)

    def redo(self):
        self._apply(self.at, self.av)

    def undo(self):
        self._apply(self.bt, self.bv)


class SetKeyTimeCommand(QUndoCommand, _ClampMixin):
    def __init__(self, tl: Timeline, key: Keyframe, old_t: float, new_t: float, label: str = "Set Time"):
        super().__init__(label)
        self.tl = tl
        self.key = key
        self.old_t = float(old_t)
        self.new_t = float(new_t)

    def redo(self):
        self.key.t = max(0.0, self.new_t)
        self._clamp(self.tl)

    def undo(self):
        self.key.t = max(0.0, self.old_t)
        self._clamp(self.tl)


class SetKeyValueCommand(QUndoCommand):
    def __init__(self, key: Keyframe, old_v: float, new_v: float, label: str = "Set Value"):
        super().__init__(label)
        self.key = key
        self.old_v = float(old_v)
        self.new_v = float(new_v)

    def redo(self):
        self.key.v = self.new_v

    def undo(self):
        self.key.v = self.old_v
