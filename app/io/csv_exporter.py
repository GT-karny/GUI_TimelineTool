import csv
from typing import Dict

from ..core.sampler import sample_timeline
from ..core.timeline import Timeline, Track


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


def export_csv(path: str, tl: Timeline, rate_hz: float = 90.0) -> None:
    ts, samples = sample_timeline(tl, rate_hz)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        collisions: Dict[str, int] = {}
        header = ["time_s"]
        for idx, (track, _) in enumerate(samples):
            header.append(_header_name(track, idx, collisions))
        w.writerow(header)

        if not samples:
            samples_values = []
        else:
            samples_values = [vals for _, vals in samples]

        for row_idx, t in enumerate(ts):
            row = [f"{float(t):.6f}"]
            for values in samples_values:
                row.append(f"{float(values[row_idx]):.6f}")
            w.writerow(row)
