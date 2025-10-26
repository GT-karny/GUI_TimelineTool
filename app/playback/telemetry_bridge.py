"""Bridge playback ticks to the telemetry sender."""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Iterable, Mapping, Optional, Tuple

from PySide6.QtCore import QSettings

from ..net.udp_sender import Endpoint, UdpSenderService
from ..telemetry.assembler import TelemetryAssembler
from ..telemetry.settings import TelemetrySettings, load_settings, save_settings


@dataclass(frozen=True)
class _TelemetrySnapshot:
    playhead_ms: int
    frame_index: int
    tracks: Tuple[dict[str, float], ...]


def _normalize_track_snapshots(
    track_snapshots: Iterable[Mapping[str, float]]
) -> Tuple[dict[str, float], ...]:
    normalized = []
    for snapshot in track_snapshots:
        name = snapshot.get("name")
        if name is None:
            continue
        value = snapshot.get("value", 0.0)
        normalized.append({"name": str(name), "value": float(value)})
    return tuple(normalized)


class TelemetryBridge:
    """Coordinates telemetry assembly and high-precision UDP transmission."""

    def __init__(self, qsettings: QSettings):
        self._qsettings = qsettings
        self.settings = load_settings(qsettings)
        self.assembler = TelemetryAssembler(session_id=self.settings.session_id)
        self.sender = UdpSenderService(Endpoint(self.settings.ip, self.settings.port))
        self.sender.start()

        self._state_lock = threading.Lock()
        self._wakeup = threading.Event()
        self._latest_snapshot: Optional[_TelemetrySnapshot] = None
        self._playing = False
        self._period_ns = self._compute_period_ns(self.settings.rate_hz)
        self._next_deadline_ns: Optional[int] = None
        self._running = True

        self._thread = threading.Thread(target=self._run, name="TelemetryBridge", daemon=True)
        self._thread.start()

    @staticmethod
    def _compute_period_ns(rate_hz: int) -> int:
        cap = max(1, min(240, int(rate_hz)))
        return max(1, int(1_000_000_000 / cap))

    def apply_settings(self, new_settings: TelemetrySettings) -> None:
        """Update runtime settings and persist them."""

        save_settings(self._qsettings, new_settings)
        updated = load_settings(self._qsettings)
        self.sender.reconfigure(Endpoint(updated.ip, updated.port))
        if updated.session_id:
            self.assembler.session_id = updated.session_id

        with self._state_lock:
            self.settings = updated
            self._period_ns = self._compute_period_ns(self.settings.rate_hz)
            self._next_deadline_ns = None
        self._wakeup.set()

    def update_snapshot(
        self,
        playing: bool,
        playhead_ms: int,
        frame_index: int,
        track_snapshots: Iterable[Mapping[str, float]],
    ) -> None:
        """Store the most recent telemetry data for background transmission."""

        snapshot = _TelemetrySnapshot(
            playhead_ms=int(playhead_ms),
            frame_index=int(frame_index),
            tracks=_normalize_track_snapshots(track_snapshots),
        )

        with self._state_lock:
            previous_playing = self._playing
            self._playing = bool(playing)
            if not self._playing:
                self._next_deadline_ns = None
            elif not previous_playing:
                self._next_deadline_ns = None
            self._latest_snapshot = snapshot

        if previous_playing != self._playing or not self._playing:
            self._wakeup.set()

    def _run(self) -> None:
        while self._running:
            with self._state_lock:
                snapshot_available = self._latest_snapshot is not None
                playing = self._playing and self.settings.enabled and snapshot_available
                period_ns = self._period_ns
                next_deadline = self._next_deadline_ns

            if not playing:
                self._wakeup.wait(timeout=0.1)
                self._wakeup.clear()
                continue

            now_ns = time.perf_counter_ns()
            if next_deadline is None:
                next_deadline = now_ns + period_ns
                with self._state_lock:
                    self._next_deadline_ns = next_deadline
                continue

            if now_ns < next_deadline:
                remaining_ns = next_deadline - now_ns
                if remaining_ns > 2_000_000:
                    wait_s = max(0.0, (remaining_ns - 1_000_000) / 1e9)
                else:
                    wait_s = max(0.0, remaining_ns / 1e9)
                self._wakeup.wait(timeout=wait_s)
                self._wakeup.clear()
                continue

            with self._state_lock:
                snapshot = self._latest_snapshot

            if snapshot is None:
                continue

            payload = self.assembler.build_payload(
                snapshot.playhead_ms, snapshot.frame_index, snapshot.tracks
            )
            self.sender.submit(payload)

            sent_ns = time.perf_counter_ns()
            next_deadline += period_ns
            if sent_ns >= next_deadline:
                while next_deadline <= sent_ns:
                    next_deadline += period_ns

            with self._state_lock:
                self._next_deadline_ns = next_deadline

    def shutdown(self) -> None:
        """Shutdown the UDP sender thread."""

        self._running = False
        self._wakeup.set()
        if self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self.sender.stop()
