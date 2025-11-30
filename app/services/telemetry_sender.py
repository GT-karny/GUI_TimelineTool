"""Helpers for constructing telemetry payloads."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List

import numpy as np

from ..core.interpolation import evaluate, evaluate_x, evaluate_y
from ..core.timeline import Timeline, Track, TrackType


@dataclass(frozen=True)
class TrackTelemetrySnapshot:
    name: str
    values: tuple[float, ...]

    def as_payload(self) -> dict[str, object]:
        return {"name": self.name, "values": list(self.values)}


def _sample_track(track: Track, playhead_s: float) -> TrackTelemetrySnapshot:
    ts = np.array([float(playhead_s)], dtype=float)
    
    # Vector2Trackの場合はX/Y両方を取得
    if getattr(track, "track_type", TrackType.SCALAR) == TrackType.VECTOR2:
        vx_values = evaluate_x(track, ts)
        vy_values = evaluate_y(track, ts)
        # [vx, vy]の順で値を結合
        values = np.concatenate([vx_values, vy_values])
    else:
        # ScalarTrackの場合は従来通り
        values = evaluate(track, ts)
    
    return TrackTelemetrySnapshot(
        name=track.name,
        values=tuple(float(v) for v in values.tolist()),
    )


def build_track_snapshots(timeline: Timeline, playhead_s: float) -> List[TrackTelemetrySnapshot]:
    """Sample all tracks at the given playhead position."""

    snapshots: List[TrackTelemetrySnapshot] = []
    for track in timeline.iter_tracks():
        snapshots.append(_sample_track(track, playhead_s))
    return snapshots


def snapshots_to_payload(
    snapshots: Iterable[TrackTelemetrySnapshot],
) -> List[dict[str, object]]:
    return [snapshot.as_payload() for snapshot in snapshots]


__all__ = ["TrackTelemetrySnapshot", "build_track_snapshots", "snapshots_to_payload"]
