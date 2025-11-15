from __future__ import annotations

from dataclasses import dataclass, field, fields, replace
from enum import Enum
from typing import Iterable, List, Mapping, Sequence, Tuple, Any
from uuid import uuid4

class InterpMode(str, Enum):
    LINEAR = "linear"
    CUBIC  = "cubic"
    STEP   = "step"
    BEZIER = "bezier"

@dataclass
class Handle:
    """Metadata describing a Bezier handle/control point."""

    t: float
    v: float

    def copy(self) -> "Handle":
        return replace(self)

    @classmethod
    def from_mapping(
        cls, mapping: Mapping[str, Any], *, default_t: float, default_v: float
    ) -> "Handle":
        data = {}
        for fld in fields(cls):
            if fld.name in mapping:
                data[fld.name] = mapping[fld.name]
        data.setdefault("t", default_t)
        data.setdefault("v", default_v)
        result = cls(**data)
        result.t = float(result.t)
        result.v = float(result.v)
        return result

    def shift_time(self, dt: float) -> None:
        self.t = float(self.t + dt)

    def shift_value(self, dv: float) -> None:
        self.v = float(self.v + dv)


@dataclass
class Keyframe:
    t: float
    v: float
    handle_in: Handle | None = None
    handle_out: Handle | None = None

    def __post_init__(self) -> None:
        self.t = float(self.t)
        self.v = float(self.v)
        self.handle_in = self._coerce_handle(self.handle_in)
        self.handle_out = self._coerce_handle(self.handle_out)

    def _coerce_handle(
        self,
        handle: Handle
        | Mapping[str, Any]
        | Sequence[float]
        | Tuple[float, float]
        | None,
    ) -> Handle:
        if handle is None:
            return Handle(self.t, self.v)
        if isinstance(handle, Handle):
            return handle.copy()
        if isinstance(handle, dict):
            coerced = Handle.from_mapping(handle, default_t=self.t, default_v=self.v)
            coerced.t = float(coerced.t)
            coerced.v = float(coerced.v)
            return coerced
        if isinstance(handle, Sequence):
            if len(handle) != 2:
                raise ValueError("Handle sequences must contain two items (t, v).")
            return Handle(float(handle[0]), float(handle[1]))
        raise TypeError("Unsupported handle data")

    def set_time(self, new_t: float) -> None:
        new_t = float(new_t)
        dt = new_t - self.t
        if abs(dt) < 1e-15:
            self.t = new_t
            return
        self.t = new_t
        if self.handle_in is not None:
            self.handle_in.shift_time(dt)
        if self.handle_out is not None:
            self.handle_out.shift_time(dt)

    def set_value(self, new_v: float) -> None:
        new_v = float(new_v)
        dv = new_v - self.v
        if abs(dv) < 1e-15:
            self.v = new_v
            return
        self.v = new_v
        if self.handle_in is not None:
            self.handle_in.shift_value(dv)
        if self.handle_out is not None:
            self.handle_out.shift_value(dv)

    def translate(self, dt: float = 0.0, dv: float = 0.0) -> None:
        if dt:
            self.set_time(self.t + dt)
        if dv:
            self.set_value(self.v + dv)

def _default_keys() -> List[Keyframe]:
    return [Keyframe(0.0, 0.0), Keyframe(5.0, 0.0)]


def _new_track_id() -> str:
    return uuid4().hex


@dataclass
class Track:
    name: str = "FloatTrack"
    interp: InterpMode = InterpMode.CUBIC
    keys: List[Keyframe] = field(default_factory=_default_keys)
    track_id: str = field(default_factory=_new_track_id)

    def sorted(self) -> List[Keyframe]:
        return sorted(self.keys, key=lambda k: (k.t, k.v))

    def clamp_times(self) -> None:
        ks = self.sorted()
        eps = 1e-9
        for i in range(1, len(ks)):
            if ks[i].t <= ks[i-1].t:
                ks[i].set_time(ks[i-1].t + eps)
        self.keys = ks

@dataclass(init=False)
class Timeline:
    duration_s: float
    tracks: List[Track]

    def __init__(
        self,
        duration_s: float = 10.0,
        tracks: Sequence[Track] | None = None,
        track: Track | None = None,
    ) -> None:
        if tracks is not None and track is not None:
            raise ValueError("Specify either 'tracks' or 'track', not both.")

        self.duration_s = max(0.001, float(duration_s))

        if tracks is not None:
            self.tracks = [self._ensure_track_instance(t) for t in tracks]
        elif track is not None:
            self.tracks = [self._ensure_track_instance(track)]
        else:
            self.tracks = [Track()]

        if not self.tracks:
            self.tracks = [Track()]

    @staticmethod
    def _ensure_track_instance(track: Track) -> Track:
        if not isinstance(track, Track):
            raise TypeError("Expected Track instances in 'tracks'.")
        if not getattr(track, "track_id", None):
            track.track_id = _new_track_id()
        return track

    def set_duration(self, d: float) -> None:
        self.duration_s = max(0.001, float(d))

    @property
    def track(self) -> Track:
        if not self.tracks:
            default = Track()
            self.tracks.append(default)
            return default
        return self.tracks[0]

    @track.setter
    def track(self, value: Track) -> None:
        replacement = self._ensure_track_instance(value)
        if self.tracks:
            self.tracks[0] = replacement
        else:
            self.tracks.append(replacement)

    def add_track(self, track: Track | None = None) -> Track:
        inst = self._ensure_track_instance(track or Track())
        self.tracks.append(inst)
        return inst

    def remove_track(self, track_id: str) -> bool:
        for idx, tr in enumerate(self.tracks):
            if tr.track_id == track_id:
                del self.tracks[idx]
                if not self.tracks:
                    self.tracks.append(Track())
                return True
        return False

    def iter_tracks(self) -> Iterable[Track]:
        return iter(self.tracks)
