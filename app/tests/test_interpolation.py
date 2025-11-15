import numpy as np

from app.core.timeline import Track, Keyframe, InterpMode, Handle
from app.core.interpolation import evaluate, eval_linear

def test_determinism_linear():
    tr = Track(interp=InterpMode.LINEAR, keys=[Keyframe(0,0), Keyframe(1,10)])
    t = np.linspace(0,1,10,endpoint=True)
    v1 = evaluate(tr, t); v2 = evaluate(tr, t)
    assert np.allclose(v1, v2)

def test_step_hold():
    tr = Track(interp=InterpMode.STEP, keys=[Keyframe(0,0), Keyframe(0.5,1), Keyframe(1.0,2)])
    t = np.array([0.0, 0.49, 0.5, 0.99])
    v = evaluate(tr, t)
    assert (v == np.array([0,0,1,1])).all()


def test_bezier_matches_expected_curve():
    bezier_track = Track(
        interp=InterpMode.BEZIER,
        keys=[
            Keyframe(0.0, 0.0, handle_out=Handle(1.0 / 3.0, 0.0)),
            Keyframe(1.0, 1.0, handle_in=Handle(2.0 / 3.0, 1.0)),
        ],
    )

    t_samples = np.linspace(0.0, 1.0, 9)
    expected = 3.0 * np.square(t_samples) - 2.0 * np.power(t_samples, 3.0)

    evaluated = evaluate(bezier_track, t_samples)
    assert np.allclose(evaluated, expected, atol=1e-9)


def test_bezier_falls_back_to_linear_for_non_monotonic_handles():
    bezier_track = Track(
        interp=InterpMode.BEZIER,
        keys=[
            Keyframe(0.0, 0.0, handle_out=Handle(0.9, -0.1)),
            Keyframe(1.0, 1.0, handle_in=Handle(0.1, 1.1)),
        ],
    )

    samples = np.linspace(-0.2, 1.2, 7)
    expected_linear = eval_linear(bezier_track, samples)
    evaluated = evaluate(bezier_track, samples)

    assert np.allclose(evaluated, expected_linear)
