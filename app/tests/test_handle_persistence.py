from __future__ import annotations

from pathlib import Path

from app.core.timeline import Timeline, Track, Keyframe, Handle, InterpMode
from app.core.history import TimelineHistory
from app.io.project_io import load_project, save_project


def _make_bezier_track() -> Track:
    return Track(
        name="Bezier",
        interp=InterpMode.BEZIER,
        keys=[
            Keyframe(0.0, 0.0, handle_out=Handle(0.25, -0.1)),
            Keyframe(0.5, 1.0, handle_in=Handle(0.4, 1.2), handle_out=Handle(0.6, 0.8)),
            Keyframe(1.0, 0.2, handle_in=Handle(0.8, 0.5)),
        ],
    )


def test_project_round_trip_preserves_handles(tmp_path: Path) -> None:
    timeline = Timeline(duration_s=5.0, tracks=[_make_bezier_track()])
    sample_rate = 144.0
    path = tmp_path / "round_trip.json"

    save_project(path, timeline, sample_rate)
    loaded_timeline, loaded_rate = load_project(path)

    assert loaded_rate == sample_rate

    loaded_track = loaded_timeline.tracks[0]
    original_track = timeline.tracks[0]

    assert loaded_track.interp == InterpMode.BEZIER
    for loaded_key, original_key in zip(loaded_track.keys, original_track.keys):
        assert loaded_key.handle_in is not None
        assert loaded_key.handle_out is not None
        assert loaded_key.handle_in.t == original_key.handle_in.t
        assert loaded_key.handle_in.v == original_key.handle_in.v
        assert loaded_key.handle_out.t == original_key.handle_out.t
        assert loaded_key.handle_out.v == original_key.handle_out.v


def test_undo_redo_restores_handle_data() -> None:
    timeline = Timeline(duration_s=2.0, tracks=[_make_bezier_track()])
    history = TimelineHistory(timeline)

    first = timeline.tracks[0].keys[0].handle_out
    second = timeline.tracks[0].keys[1].handle_in
    assert first is not None
    assert second is not None

    # State B
    first.t, first.v = 0.3, -0.25
    second.t, second.v = 0.55, 1.35
    history.push()

    # State C
    first.t, first.v = 0.45, -0.05
    second.t, second.v = 0.65, 0.95
    history.push()

    # Mutate without pushing (state D)
    first.t, first.v = 0.1, 0.0
    second.t, second.v = 0.9, 1.6

    assert history.undo() is True
    assert abs(first.t - 0.3) < 1e-12
    assert abs(first.v + 0.25) < 1e-12
    assert abs(second.t - 0.55) < 1e-12
    assert abs(second.v - 1.35) < 1e-12

    assert history.redo() is True
    assert abs(first.t - 0.45) < 1e-12
    assert abs(first.v + 0.05) < 1e-12
    assert abs(second.t - 0.65) < 1e-12
    assert abs(second.v - 0.95) < 1e-12
