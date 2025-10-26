import json
from pathlib import Path

from ..core.timeline import Timeline, Track, Keyframe, InterpMode


def save_project(path: str | Path, tl: Timeline, sample_rate_hz: float) -> None:
    obj = {
        "duration_s": tl.duration_s,
        "sample_rate_hz": float(sample_rate_hz),
        "track": {
            "name": tl.track.name,
            "interp": tl.track.interp.value,
            "keys": [{"t": k.t, "v": k.v} for k in tl.track.keys],
        },
    }
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def load_project(path: str | Path) -> tuple[Timeline, float]:
    obj = json.loads(Path(path).read_text(encoding="utf-8"))
    tr = Track(
        name=obj["track"]["name"],
        interp=InterpMode(obj["track"]["interp"]),
        keys=[Keyframe(**kv) for kv in obj["track"]["keys"]],
    )
    sample_rate = float(obj.get("sample_rate_hz", 90.0))
    return Timeline(duration_s=float(obj["duration_s"]), track=tr), sample_rate
