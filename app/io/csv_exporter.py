import csv
from ..core.sampler import sample_timeline
from ..core.timeline import Timeline

def export_csv(path: str, tl: Timeline, rate_hz: float = 90.0) -> None:
    ts, vs = sample_timeline(tl, rate_hz)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["time_s", "value"])
        for t, v in zip(ts, vs):
            w.writerow([f"{t:.6f}", f"{v:.6f}"])
