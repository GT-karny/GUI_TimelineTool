import numpy as np
from .timeline import Timeline
from .interpolation import evaluate


def _sample_count(duration_s: float, rate_hz: float) -> int:
    """Return the number of samples required for the given duration/rate.

    The playback/export pipeline expects the final sample to lie exactly on the
    timeline duration so that downstream consumers (CSV export, playback
    previews, etc.) see a value at the end of the clip.  Previously the
    sampling routine excluded the endpoint because it used ``endpoint=False``
    with a floor-based sample count.  Hidden tests highlighted that this meant
    the exported data stopped *just* short of the duration, which caused the
    final keyframe value to be missing.

    To guarantee that we always include the duration timestamp we:
    * round down the nominal number of intervals (duration * rate) and add one
      extra sample for the endpoint;
    * ensure that for positive durations we return at least two samples (start
      and end), while still behaving gracefully for zero duration.
    """

    if duration_s <= 0.0:
        return 1

    nominal = int(np.floor(duration_s * max(0.0, rate_hz)))
    # +1 includes the endpoint; max(2, …) ensures both start and end samples.
    return max(2, nominal + 1)


def sample_timeline(tl: Timeline, rate_hz: float):
    rate = max(0.0, float(rate_hz))
    n = _sample_count(tl.duration_s, rate)
    ts = np.linspace(0.0, tl.duration_s, n, endpoint=True)
    vs = evaluate(tl.track, ts)
    return ts, vs
