import numpy as np
from app.core.timeline import Track, Keyframe, InterpMode
from app.core.interpolation import evaluate

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
