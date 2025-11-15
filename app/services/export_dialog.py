"""CSV export dialog helpers."""
from __future__ import annotations

from typing import Callable, Sequence

from PySide6 import QtWidgets

from ..core.timeline import Timeline
from ..io.csv_exporter import CsvTable, build_csv_header, build_csv_table, write_csv


SaveDialogFn = Callable[[QtWidgets.QWidget | None, str, str, str], tuple[str, str]]
MessageFn = Callable[[QtWidgets.QWidget | None, str, str], None]


def _expected_header(timeline: Timeline) -> Sequence[str]:
    tracks = list(timeline.iter_tracks())
    return build_csv_header(tracks)


def _validate_table(table: CsvTable, timeline: Timeline) -> None:
    expected = list(_expected_header(timeline))
    if list(table.header) != expected:
        raise ValueError(
            f"CSV header mismatch: expected {expected!r} got {list(table.header)!r}"
        )

    expected_cols = len(expected)
    for idx, row in enumerate(table.rows):
        if len(row) != expected_cols:
            raise ValueError(f"Row {idx} has {len(row)} columns (expected {expected_cols})")


def export_timeline_csv_via_dialog(
    parent: QtWidgets.QWidget | None,
    timeline: Timeline,
    sample_rate_hz: float,
    *,
    save_dialog: SaveDialogFn | None = None,
    message_box: MessageFn | None = None,
) -> bool:
    """Prompt for a path and export the timeline to CSV."""

    dialog = save_dialog or QtWidgets.QFileDialog.getSaveFileName
    msg = message_box or QtWidgets.QMessageBox.information

    path, _ = dialog(parent, "Export CSV", "timeline.csv", "CSV Files (*.csv)")
    if not path:
        return False

    table = build_csv_table(timeline, float(sample_rate_hz))
    _validate_table(table, timeline)
    write_csv(path, table)

    if msg is not None:
        msg(parent, "Export", f"Exported to:\n{path}")
    return True


__all__ = ["export_timeline_csv_via_dialog"]
