from __future__ import annotations

import csv
from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence, Tuple

from ..core.sampler import sample_timeline
from ..core.timeline import Timeline, Track


@dataclass(frozen=True)
class CsvTable:
    """Immutable representation of a CSV export table."""

    header: Tuple[str, ...]
    rows: Tuple[Tuple[str, ...], ...]

    @property
    def column_count(self) -> int:
        return len(self.header)

    @property
    def row_count(self) -> int:
        return len(self.rows)


def _header_name(track: Track, index: int, collisions: Dict[str, int]) -> str:
    base = track.name.strip() if track.name else f"{index + 1}"
    safe = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in base)
    if not safe:
        safe = f"{index + 1}"
    key = safe.lower()
    count = collisions.get(key, 0)
    collisions[key] = count + 1
    if count > 0:
        safe = f"{safe}_{count+1}"
    return f"track_{safe}"


def build_csv_header(tracks: Sequence[Track]) -> List[str]:
    collisions: Dict[str, int] = {}
    header = ["time_s"]
    for idx, track in enumerate(tracks):
        header.append(_header_name(track, idx, collisions))
    return header


def build_csv_table(tl: Timeline, rate_hz: float = 90.0) -> CsvTable:
    """Sample the timeline and return a table suitable for CSV export."""

    ts, samples = sample_timeline(tl, rate_hz)
    tracks = [track for track, _ in samples]
    header = build_csv_header(tracks)

    sample_values: List[Sequence[float]] = [vals for _, vals in samples]
    rows: List[Tuple[str, ...]] = []
    for row_idx, t in enumerate(ts):
        row: List[str] = [f"{float(t):.6f}"]
        for values in sample_values:
            row.append(f"{float(values[row_idx]):.6f}")
        rows.append(tuple(row))

    return CsvTable(tuple(header), tuple(rows))


def write_csv(path: str, table: CsvTable) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(table.header)
        writer.writerows(table.rows)


def export_csv(path: str, tl: Timeline, rate_hz: float = 90.0) -> CsvTable:
    """Convenience wrapper that builds and writes a CSV table."""

    table = build_csv_table(tl, rate_hz)
    write_csv(path, table)
    return table


def iter_csv_rows(table: CsvTable) -> Iterable[Tuple[str, ...]]:
    yield table.header
    yield from table.rows
