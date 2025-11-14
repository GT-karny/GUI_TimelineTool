"""Telemetry payload assembler for UDP transport."""
from __future__ import annotations

import json
import uuid
from collections.abc import Iterable, Mapping

from app.version import APP_VERSION


class TelemetryAssembler:
    """Builds compact JSON telemetry payloads."""

    def __init__(self, session_id: str | None = None):
        self.session_id = session_id or str(uuid.uuid4())

    def build_payload(
        self,
        playhead_ms: int,
        frame_index: int,
        track_snapshots: Iterable[Mapping[str, object]],
    ) -> bytes:
        """Convert timeline data into a JSON payload."""

        def _values(snapshot: Mapping[str, object]) -> list[float]:
            raw = snapshot.get("values")
            if raw is None and "value" in snapshot:
                raw = [snapshot.get("value")]
            if raw is None:
                raw_iterable = []
            elif isinstance(raw, Mapping):
                raw_iterable = raw.values()
            elif isinstance(raw, (str, bytes)):
                raw_iterable = [raw]
            else:
                try:
                    raw_iterable = list(raw)  # type: ignore[arg-type]
                except TypeError:
                    raw_iterable = [raw]

            values: list[float] = []
            for value in raw_iterable:
                try:
                    values.append(float(value))
                except (TypeError, ValueError):
                    continue
            return values

        doc = {
            "version": APP_VERSION,
            "session_id": self.session_id,
            "timestamp_ms": int(playhead_ms),
            "frame_index": int(frame_index),
            "tracks": [],
        }
        for snapshot in track_snapshots:
            name = snapshot.get("name")
            if name is None:
                continue
            doc["tracks"].append({"name": str(name), "values": _values(snapshot)})
        return json.dumps(doc, separators=(",", ":")).encode("utf-8")
