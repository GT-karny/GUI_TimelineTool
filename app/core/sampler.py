import numpy as np
from typing import List, Tuple

from .timeline import Timeline, Track
from .interpolation import evaluate

def sample_timeline(tl: Timeline, rate_hz: float) -> Tuple[np.ndarray, List[Tuple[Track, np.ndarray]]]:
    rate = max(1.0, float(rate_hz))
    n = max(1, int(np.floor(tl.duration_s * rate)))
    ts = np.linspace(0.0, tl.duration_s, n, endpoint=False)
    ts = np.clip(ts, 0.0, tl.duration_s)
    samples: List[Tuple[Track, np.ndarray]] = []
    for track in tl.tracks:
        track.clamp_times()
        samples.append((track, evaluate(track, ts)))
    return ts, samples
