import csv

from app.core.timeline import Keyframe, Timeline, Track
from app.io.csv_exporter import build_csv_header, build_csv_table, write_csv


def _make_track(name: str, value: float) -> Track:
    track = Track(name=name)
    track.keys = [Keyframe(0.0, value), Keyframe(1.0, value + 1.0)]
    return track


def test_build_csv_table_uses_multitrack_header(tmp_path):
    timeline = Timeline(
        duration_s=1.0,
        tracks=[
            _make_track("Camera.FOV", 10.0),
            _make_track("Camera FOV", 20.0),
            _make_track("", 30.0),
        ],
    )

    table = build_csv_table(timeline, rate_hz=2.0)
    expected_header = build_csv_header(timeline.tracks)

    assert list(table.header) == expected_header
    for row in table.rows:
        assert len(row) == len(expected_header)

    out_path = tmp_path / "export.csv"
    write_csv(out_path.as_posix(), table)

    with out_path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.reader(fh)
        rows = list(reader)

    assert rows[0] == expected_header
    assert len(rows) == table.row_count + 1
