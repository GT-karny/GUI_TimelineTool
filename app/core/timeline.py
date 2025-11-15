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


def initialize_handle_positions(
    track: "Track",
    key: Keyframe,
    *,
    fraction: float = 1.0 / 3.0,
    eps: float = 1e-9,
) -> None:
    """Separate newly-created Bezier handles from the key position."""

    if getattr(track, "interp", None) != InterpMode.BEZIER:
        return

    handle_in = key.handle_in
    handle_out = key.handle_out

    if handle_in is None and handle_out is None:
        return

    keys = track.sorted()
    try:
        idx = keys.index(key)
    except ValueError:  # pragma: no cover - defensive
        return

    prev_key = keys[idx - 1] if idx > 0 else None
    next_key = keys[idx + 1] if idx + 1 < len(keys) else None

    def _needs_adjust(handle: Handle | None) -> bool:
        if handle is None:
            return False
        return abs(handle.t - key.t) < eps and abs(handle.v - key.v) < eps

    def _fallback_span() -> float:
        if len(keys) < 2:
            return 1.0
        span_candidates = [
            abs(keys[i + 1].t - keys[i].t) for i in range(len(keys) - 1)
        ]
        span = max(span_candidates, default=1.0)
        return span if span > eps else 1.0

    def _apply_defaults(handle: Handle | None, direction: str) -> None:
        if handle is None or not _needs_adjust(handle):
            return

        target_t = key.t
        target_v = key.v

        if direction == "in":
            source = prev_key
            fallback_source = next_key
        else:
            source = next_key
            fallback_source = prev_key

        segment = None
        if source is not None and abs(source.t - key.t) > eps:
            segment = source
        elif fallback_source is not None and abs(fallback_source.t - key.t) > eps:
            segment = fallback_source

        if segment is not None:
            if direction == "in" and segment.t > key.t:
                span_t = segment.t - key.t
                slope = (segment.v - key.v) / span_t
                dt = span_t * fraction
                target_t = key.t - dt
                target_v = key.v - slope * dt
            elif direction == "out" and segment.t < key.t:
                span_t = key.t - segment.t
                slope = (key.v - segment.v) / span_t
                dt = span_t * fraction
                target_t = key.t + dt
                target_v = key.v + slope * dt
            else:
                span_t = abs(segment.t - key.t)
                slope = (segment.v - key.v) / (segment.t - key.t)
                dt = span_t * fraction
                if direction == "in":
                    target_t = key.t - dt
                    target_v = key.v - slope * dt
                else:
                    target_t = key.t + dt
                    target_v = key.v + slope * dt
        else:
            span_t = _fallback_span() * fraction
            if direction == "in":
                target_t = key.t - span_t
                target_v = key.v
            else:
                target_t = key.t + span_t
                target_v = key.v

        if direction == "in":
            target_t = max(0.0, target_t)

        if abs(target_t - key.t) < eps and abs(target_v - key.v) < eps:
            if direction == "in":
                target_v = key.v - 1e-3
            else:
                target_v = key.v + 1e-3

        handle.t = float(target_t)
        handle.v = float(target_v)

    _apply_defaults(handle_in, "in")
    _apply_defaults(handle_out, "out")

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
    _init_handles: bool = field(default=True, repr=False, compare=False)

    def __post_init__(self) -> None:
        if not self._init_handles or self.interp != InterpMode.BEZIER:
            return

        for key in list(self.keys):
            initialize_handle_positions(self, key)

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
