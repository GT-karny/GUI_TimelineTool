import numpy as np

from app.core.interpolation import eval_bezier, evaluate
from app.core.timeline import InterpMode, Keyframe, Track


def _create_bezier_track() -> Track:
    k0 = Keyframe(0.0, 0.0, handle_out=(1.0, 0.2))
    k1 = Keyframe(3.0, 1.0, handle_in=(2.0, 0.8))
    track = Track(interp=InterpMode.BEZIER, keys=[k0, k1])
    return track


def test_eval_bezier_matches_expected_curve():
    track = _create_bezier_track()
    ts = np.linspace(0.0, 3.0, 7)
    values = eval_bezier(track, ts)

    # With linearly spaced time control points, parameter u is t / 3
    expected = []
    for t in ts:
        u = t / 3.0
        omu = 1.0 - u
        expected.append(
            (omu ** 3) * 0.0
            + 3 * (omu ** 2) * u * 0.2
            + 3 * omu * (u ** 2) * 0.8
            + (u ** 3) * 1.0
        )
    np.testing.assert_allclose(values, np.array(expected), atol=1e-6)


def test_eval_bezier_linear_fallback_when_handles_invalid():
    k0 = Keyframe(0.0, 0.0, handle_out=(-1.0, -1.0))
    k1 = Keyframe(2.0, 2.0, handle_in=(-0.5, 3.0))
    track = Track(interp=InterpMode.BEZIER, keys=[k0, k1])

    ts = np.linspace(0.0, 2.0, 5)
    values = eval_bezier(track, ts)
    expected = np.linspace(0.0, 2.0, 5)
    np.testing.assert_allclose(values, expected, atol=1e-8)


def test_evaluate_bezier_used_by_sampler():
    track = _create_bezier_track()
    ts = np.array([0.0, 1.5, 2.5])
    values = evaluate(track, ts)
    assert values.shape == ts.shape
    assert np.all(np.isfinite(values))
