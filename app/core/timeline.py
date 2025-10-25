from dataclasses import dataclass, field
from enum import Enum
from typing import List

class InterpMode(str, Enum):
    LINEAR = "linear"
    CUBIC  = "cubic"
    STEP   = "step"

@dataclass
class Keyframe:
    t: float
    v: float

@dataclass
class Track:
    name: str = "FloatTrack"
    interp: InterpMode = InterpMode.CUBIC
    keys: List[Keyframe] = field(default_factory=lambda: [Keyframe(0.0, 0.0), Keyframe(5.0, 0.0)])

    def sorted(self) -> List[Keyframe]:
        return sorted(self.keys, key=lambda k: (k.t, k.v))

    def clamp_times(self) -> None:
        ks = self.sorted()
        eps = 1e-9
        for i in range(1, len(ks)):
            if ks[i].t <= ks[i-1].t:
                ks[i].t = ks[i-1].t + eps
        self.keys = ks

@dataclass
class Timeline:
    duration_s: float = 10.0
    track: Track = field(default_factory=Track)

    def set_duration(self, d: float) -> None:
        self.duration_s = max(0.001, float(d))
