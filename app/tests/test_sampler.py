import numpy as np

from app.core.timeline import Timeline, Track, Keyframe, InterpMode
from app.core.sampler import sample_timeline


def _timeline(duration: float = 1.0) -> Timeline:
    tl = Timeline(duration_s=duration, track=Track(interp=InterpMode.LINEAR))
    tl.track.keys = [Keyframe(0.0, 0.0), Keyframe(duration, 1.0)]
    tl.track.clamp_times()
    return tl


def test_samples_include_endpoint():
    tl = _timeline(1.0)
    ts, vs = sample_timeline(tl, rate_hz=2.0)

    # Expect three samples: 0.0, 0.5, 1.0
    assert np.allclose(ts, np.array([0.0, 0.5, 1.0]))
    assert np.allclose(vs, np.array([0.0, 0.5, 1.0]))


def test_zero_duration_returns_single_sample():
    tl = _timeline(duration=0.0)
    ts, vs = sample_timeline(tl, rate_hz=30.0)

    assert ts.shape == (1,)
    assert vs.shape == (1,)
    assert ts[0] == 0.0
    assert vs[0] == 0.0
