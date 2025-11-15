import numpy as np
try:
    from scipy.interpolate import CubicSpline
    HAVE_SCIPY = True
except Exception:
    HAVE_SCIPY = False

from .timeline import Track, InterpMode

def _sorted_arrays(track: Track):
    ks = track.sorted()
    t = np.array([k.t for k in ks], dtype=float)
    v = np.array([k.v for k in ks], dtype=float)
    return t, v

def eval_linear(track: Track, t_eval: np.ndarray) -> np.ndarray:
    t, v = _sorted_arrays(track)
    if len(t) == 0:
        return np.zeros_like(t_eval, dtype=float)
    if len(t) == 1:
        return np.full_like(t_eval, v[0], dtype=float)
    return np.interp(t_eval, t, v, left=v[0], right=v[-1])

def eval_step(track: Track, t_eval: np.ndarray) -> np.ndarray:
    t, v = _sorted_arrays(track)
    if len(t) == 0:
        return np.zeros_like(t_eval, dtype=float)
    if len(t) == 1:
        return np.full_like(t_eval, v[0], dtype=float)
    idxs = np.searchsorted(t, t_eval, side="right") - 1
    idxs = np.clip(idxs, 0, len(v)-1)
    return v[idxs]

def eval_cubic(track: Track, t_eval: np.ndarray) -> np.ndarray:
    t, v = _sorted_arrays(track)
    if len(t) < 3 or not HAVE_SCIPY or np.any(np.diff(t) <= 0):
        return eval_linear(track, t_eval)
    cs = CubicSpline(t, v, bc_type="natural", extrapolate=True)
    return cs(t_eval)

def evaluate(track: Track, t_eval: np.ndarray) -> np.ndarray:
    if track.interp == InterpMode.LINEAR:
        return eval_linear(track, t_eval)
    if track.interp == InterpMode.STEP:
        return eval_step(track, t_eval)
    if track.interp == InterpMode.BEZIER:
        return eval_cubic(track, t_eval)
    return eval_cubic(track, t_eval)
