import numpy as np
try:
    from scipy.interpolate import CubicSpline
    HAVE_SCIPY = True
except Exception:
    HAVE_SCIPY = False

from .timeline import Track, InterpMode, Keyframe

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


def _cubic_bezier(u: float, p0: float, p1: float, p2: float, p3: float) -> float:
    omu = 1.0 - u
    return (
        (omu ** 3) * p0
        + 3.0 * (omu ** 2) * u * p1
        + 3.0 * omu * (u ** 2) * p2
        + (u ** 3) * p3
    )


def _cubic_bezier_derivative(u: float, p0: float, p1: float, p2: float, p3: float) -> float:
    omu = 1.0 - u
    return 3.0 * (
        (omu ** 2) * (p1 - p0)
        + 2.0 * omu * u * (p2 - p1)
        + (u ** 2) * (p3 - p2)
    )


def _segment_is_monotonic(ctrl_t: np.ndarray) -> bool:
    if not np.all(np.isfinite(ctrl_t)):
        return False
    if ctrl_t[3] - ctrl_t[0] <= 1e-9:
        return False
    if np.any(np.diff(ctrl_t) < -1e-9):
        return False
    return True


def _evaluate_linear_segment(
    t0: float, t1: float, v0: float, v1: float, t_eval: np.ndarray
) -> np.ndarray:
    if abs(t1 - t0) <= 1e-12:
        return np.full_like(t_eval, v0, dtype=float)
    frac = (t_eval - t0) / (t1 - t0)
    return v0 + frac * (v1 - v0)


def _solve_segment_parameter(target: float, ctrl_t: np.ndarray) -> float:
    p0, p1, p2, p3 = ctrl_t
    if target <= p0:
        return 0.0
    if target >= p3:
        return 1.0

    span = p3 - p0
    if span <= 1e-12:
        return 0.0

    u = np.clip((target - p0) / span, 0.0, 1.0)

    for _ in range(8):
        value = _cubic_bezier(u, p0, p1, p2, p3)
        derivative = _cubic_bezier_derivative(u, p0, p1, p2, p3)
        if abs(derivative) <= 1e-12:
            break
        step = (value - target) / derivative
        u_new = np.clip(u - step, 0.0, 1.0)
        if abs(u_new - u) <= 1e-8:
            u = u_new
            break
        u = u_new

    if abs(_cubic_bezier(u, p0, p1, p2, p3) - target) > 1e-6:
        low, high = 0.0, 1.0
        for _ in range(24):
            mid = 0.5 * (low + high)
            value = _cubic_bezier(mid, p0, p1, p2, p3)
            if value < target:
                low = mid
            else:
                high = mid
        u = 0.5 * (low + high)

    return float(u)


def _eval_bezier_segment(k0: Keyframe, k1: Keyframe, t_eval: np.ndarray) -> np.ndarray:
    ctrl_t = np.array(
        [k0.t, k0.handle_out.t, k1.handle_in.t, k1.t], dtype=float
    )
    if not _segment_is_monotonic(ctrl_t):
        return _evaluate_linear_segment(k0.t, k1.t, k0.v, k1.v, t_eval)

    ctrl_v = np.array(
        [k0.v, k0.handle_out.v, k1.handle_in.v, k1.v], dtype=float
    )

    result = np.empty_like(t_eval, dtype=float)
    for idx, target in enumerate(t_eval):
        u = _solve_segment_parameter(float(target), ctrl_t)
        result[idx] = _cubic_bezier(u, *ctrl_v)
    return result


def eval_bezier(track: Track, t_eval: np.ndarray) -> np.ndarray:
    t_eval = np.asarray(t_eval, dtype=float)
    keys = track.sorted()
    if not keys:
        return np.zeros_like(t_eval, dtype=float)
    if len(keys) == 1:
        return np.full_like(t_eval, keys[0].v, dtype=float)

    ts = np.array([k.t for k in keys], dtype=float)
    vs = np.array([k.v for k in keys], dtype=float)

    idxs = np.searchsorted(ts, t_eval, side="right") - 1
    result = np.empty_like(t_eval, dtype=float)

    mask_before = idxs < 0
    result[mask_before] = vs[0]

    mask_after = idxs >= len(ts) - 1
    result[mask_after] = vs[-1]

    mask_mid = ~(mask_before | mask_after)
    if np.any(mask_mid):
        mid_ts = t_eval[mask_mid]
        mid_idxs = idxs[mask_mid]
        mid_result = np.empty_like(mid_ts, dtype=float)

        for seg_idx in np.unique(mid_idxs):
            seg_mask = mid_idxs == seg_idx
            seg_times = mid_ts[seg_mask]
            segment_values = _eval_bezier_segment(
                keys[seg_idx], keys[seg_idx + 1], seg_times
            )
            mid_result[seg_mask] = segment_values

        result[mask_mid] = mid_result

    return result

def evaluate(track: Track, t_eval: np.ndarray) -> np.ndarray:
    if track.interp == InterpMode.LINEAR:
        return eval_linear(track, t_eval)
    if track.interp == InterpMode.STEP:
        return eval_step(track, t_eval)
    if track.interp == InterpMode.BEZIER:
        return eval_bezier(track, t_eval)
    return eval_cubic(track, t_eval)
