from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable, List, Sequence
from uuid import uuid4

class InterpMode(str, Enum):
    LINEAR = "linear"
    CUBIC  = "cubic"
    STEP   = "step"

@dataclass
class Keyframe:
    t: float
    v: float

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
                ks[i].t = ks[i-1].t + eps
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
