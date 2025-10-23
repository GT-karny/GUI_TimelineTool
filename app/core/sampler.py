import numpy as np
from .timeline import Timeline
from .interpolation import evaluate

def sample_timeline(tl: Timeline, rate_hz: float):
    rate = max(1.0, float(rate_hz))
    n = max(1, int(np.floor(tl.duration_s * rate)))
    ts = np.linspace(0.0, tl.duration_s, n, endpoint=False)
    vs = evaluate(tl.track, ts)
    return ts, vs
