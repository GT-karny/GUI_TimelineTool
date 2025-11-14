import csv

import pytest

from app.core.history import TimelineHistory
from app.core.timeline import Keyframe, Track
from app.io.csv_exporter import build_csv_table, write_csv


def test_multitrack_csv_export_has_unique_columns(multitrack_project, tmp_path):
    timeline, sample_rate = multitrack_project

    table = build_csv_table(timeline, rate_hz=sample_rate)
    expected_header = ["time_s", "track_Camera_FOV", "track_Camera_FOV_2", "track_3"]

    assert list(table.header) == expected_header
    assert table.column_count == len(expected_header)
    assert table.row_count > 0
    assert all(len(row) == table.column_count for row in table.rows)

    out_path = tmp_path / "timeline.csv"
    write_csv(out_path.as_posix(), table)

    with out_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        rows = list(reader)

    assert rows[0] == expected_header
    assert len(rows) == table.row_count + 1


def test_project_data_compatibility(loaded_project):
    timeline, sample_rate, label = loaded_project

    assert sample_rate > 0.0
    assert len(timeline.tracks) >= 1

    if label == "multitrack":
        assert sample_rate == pytest.approx(90.0)
        assert len(timeline.tracks) == 3
        names = [track.name for track in timeline.tracks]
        assert names == ["Camera.FOV", "Camera FOV", "   "]
    else:
        assert sample_rate == pytest.approx(120.0)
        assert len(timeline.tracks) == 1
        assert timeline.track.name == "Legacy Float"


def test_timeline_history_tracks_support_undo_redo(multitrack_project):
    timeline, _ = multitrack_project
    history = TimelineHistory(timeline)
    baseline_ids = [track.track_id for track in timeline.tracks]

    extra_track = Track(
        name="Additional Track",
        keys=[Keyframe(0.0, -1.0), Keyframe(1.0, 1.0)],
    )
    added_track = timeline.add_track(extra_track)
    history.push()

    assert added_track.track_id not in baseline_ids
    assert [track.track_id for track in timeline.tracks][-1] == added_track.track_id

    removed = timeline.remove_track(added_track.track_id)
    history.push()

    assert removed is True
    assert [track.track_id for track in timeline.tracks] == baseline_ids

    assert history.undo() is True
    ids_after_undo = [track.track_id for track in timeline.tracks]
    assert added_track.track_id in ids_after_undo
    restored = next(track for track in timeline.tracks if track.track_id == added_track.track_id)
    assert restored.name == "Additional Track"
    assert restored.keys[0].v == pytest.approx(-1.0)

    assert history.undo() is True
    assert [track.track_id for track in timeline.tracks] == baseline_ids

    assert history.redo() is True
    ids_after_redo = [track.track_id for track in timeline.tracks]
    assert added_track.track_id in ids_after_redo

    assert history.redo() is True
    assert [track.track_id for track in timeline.tracks] == baseline_ids
