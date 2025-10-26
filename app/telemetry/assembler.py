"""Telemetry payload assembler for UDP transport."""
from __future__ import annotations

import json
import uuid
from typing import Iterable, Mapping


class TelemetryAssembler:
    """Builds compact JSON telemetry payloads."""

    def __init__(self, session_id: str | None = None):
        self.session_id = session_id or str(uuid.uuid4())

    def build_payload(
        self,
        playhead_ms: int,
        frame_index: int,
        track_snapshots: Iterable[Mapping[str, float]],
    ) -> bytes:
        """Convert timeline data into a JSON payload."""

        doc = {
            "version": "1.0",
            "session_id": self.session_id,
            "timestamp_ms": int(playhead_ms),
            "frame_index": int(frame_index),
            "tracks": [
                {"name": snapshot["name"], "value": float(snapshot["value"])}
                for snapshot in track_snapshots
            ],
        }
        return json.dumps(doc, separators=(",", ":")).encode("utf-8")
