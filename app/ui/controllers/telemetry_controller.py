from __future__ import annotations

from typing import Callable, TYPE_CHECKING

from ...services.telemetry_sender import build_track_snapshots, snapshots_to_payload
from ...telemetry.settings import TelemetrySettings

if TYPE_CHECKING:  # pragma: no cover - imported for type checking only
    from ...playback.controller import PlaybackController
    from ...playback.telemetry_bridge import TelemetryBridge
    from ..telemetry_panel import TelemetryPanel
    from ...core.timeline import Timeline


class TelemetryController:
    """Manages telemetry updates for the main window."""

    def __init__(
        self,
        *,
        playback: "PlaybackController",
        telemetry_bridge: "TelemetryBridge",
        telemetry_panel: "TelemetryPanel",
        timeline_getter: Callable[[], "Timeline"],
        snapshot_builder: Callable[["Timeline", float], object] = build_track_snapshots,
        payload_builder: Callable[[object], object] = snapshots_to_payload,
    ) -> None:
        self._playback = playback
        self._telemetry_bridge = telemetry_bridge
        self._telemetry_panel = telemetry_panel
        self._timeline_getter = timeline_getter
        self._snapshot_builder = snapshot_builder
        self._payload_builder = payload_builder
        self._telemetry_frame_index = 0

    # -------------------- Initialization --------------------
    def initialize_panel(self) -> None:
        self._telemetry_panel.set_settings(
            self._telemetry_bridge.settings,
            session_placeholder=self._telemetry_bridge.assembler.session_id,
        )

    # -------------------- Playback hooks --------------------
    def on_playback_playhead_changed(self, playhead_s: float, playing: bool) -> None:
        self._publish_snapshot(playhead_s, playing, advance_frame=playing)

    def on_playback_state_changed(self, playing: bool) -> None:
        if playing:
            self._telemetry_frame_index = 0
        self._publish_snapshot(self._playback.playhead, playing, advance_frame=False)

    # -------------------- Telemetry panel hooks --------------------
    def on_settings_changed(self, settings: TelemetrySettings) -> None:
        self._telemetry_bridge.apply_settings(settings)
        self._telemetry_panel.set_settings(
            self._telemetry_bridge.settings,
            session_placeholder=self._telemetry_bridge.assembler.session_id,
        )

    # -------------------- Shutdown --------------------
    def shutdown(self) -> None:
        self._telemetry_bridge.shutdown()

    # -------------------- Internal helpers --------------------
    def _publish_snapshot(self, playhead_s: float, playing: bool, *, advance_frame: bool) -> None:
        frame_index = self._telemetry_frame_index
        self._send_snapshot(playing, playhead_s, frame_index)
        if advance_frame:
            self._telemetry_frame_index = frame_index + 1

    def _send_snapshot(self, playing: bool, playhead_s: float, frame_index: int) -> None:
        timeline = self._timeline_getter()
        snapshots = self._snapshot_builder(timeline, playhead_s)
        payload = self._payload_builder(snapshots)
        self._telemetry_bridge.update_snapshot(
            playing=playing,
            playhead_ms=int(playhead_s * 1000),
            frame_index=frame_index,
            track_snapshots=payload,
        )
