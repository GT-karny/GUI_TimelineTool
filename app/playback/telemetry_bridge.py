"""Bridge playback ticks to the telemetry sender."""
from __future__ import annotations

import time
from typing import Iterable, Mapping

from PySide6.QtCore import QSettings

from ..net.udp_sender import Endpoint, UdpSenderService
from ..telemetry.assembler import TelemetryAssembler
from ..telemetry.settings import TelemetrySettings, load_settings, save_settings


class TelemetryBridge:
    """Coordinates telemetry assembly and UDP transmission."""

    def __init__(self, qsettings: QSettings):
        self._qsettings = qsettings
        self.settings = load_settings(qsettings)
        self.assembler = TelemetryAssembler(session_id=self.settings.session_id)
        self.sender = UdpSenderService(Endpoint(self.settings.ip, self.settings.port))
        self.sender.start()
        self._last_sent_ns = 0

    def apply_settings(self, new_settings: TelemetrySettings) -> None:
        """Update runtime settings and persist them."""

        save_settings(self._qsettings, new_settings)
        self.settings = load_settings(self._qsettings)
        self.sender.reconfigure(Endpoint(self.settings.ip, self.settings.port))
        if self.settings.session_id:
            self.assembler.session_id = self.settings.session_id
        self._last_sent_ns = 0

    def maybe_send_frame(
        self,
        playing: bool,
        playhead_ms: int,
        frame_index: int,
        track_snapshots: Iterable[Mapping[str, float]],
    ) -> None:
        """Send the latest telemetry frame if enabled and within rate cap."""

        if not playing or not self.settings.enabled:
            return

        cap = max(1, min(240, int(self.settings.rate_hz)))
        now_ns = time.time_ns()
        period_ns = int(1e9 / cap)
        if now_ns - self._last_sent_ns < period_ns:
            return
        self._last_sent_ns = now_ns

        payload = self.assembler.build_payload(playhead_ms, frame_index, track_snapshots)
        self.sender.submit(payload)

    def shutdown(self) -> None:
        """Shutdown the UDP sender thread."""

        self.sender.stop()
