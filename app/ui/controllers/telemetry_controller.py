from __future__ import annotations

from typing import Callable, Optional, TYPE_CHECKING

from ...services.telemetry_sender import build_track_snapshots, snapshots_to_payload
from ...telemetry.settings import TelemetrySettings
from ...net.udp_receiver import UdpReceiverService

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

        # Sync mode receiver
        self._sync_receiver = UdpReceiverService(
            port=9001,
            on_receive=self._on_sync_packet_received
        )
        # Apply initial settings
        self._apply_sync_settings(self._telemetry_bridge.settings)

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
        self._apply_sync_settings(settings)
        self._telemetry_panel.set_settings(
            self._telemetry_bridge.settings,
            session_placeholder=self._telemetry_bridge.assembler.session_id,
        )

    def _apply_sync_settings(self, settings: TelemetrySettings) -> None:
        if settings.sync_enabled:
            self._sync_receiver.reconfigure(settings.sync_port)
            self._sync_receiver.start()
        else:
            self._sync_receiver.stop()

    def get_debug_log_state(self) -> bool:
        return self._telemetry_bridge.settings.debug_log

    def set_debug_log(self, enabled: bool) -> None:
        """Update debug log setting."""
        current = self._telemetry_bridge.settings
        new_settings = TelemetrySettings(
            enabled=current.enabled,
            ip=current.ip,
            port=current.port,
            rate_hz=current.rate_hz,
            session_id=current.session_id,
            sync_enabled=current.sync_enabled,
            sync_port=current.sync_port,
            debug_log=enabled,
        )
        self.on_settings_changed(new_settings)

    # -------------------- Shutdown --------------------
    def shutdown(self) -> None:
        self._telemetry_bridge.shutdown()
        self._sync_receiver.stop()

    # -------------------- Sync Mode --------------------
    def _on_sync_packet_received(self, time_s: float) -> None:
        """Callback when a sync packet is received."""
        if self._telemetry_bridge.settings.debug_log:
            print(f"DEBUG: Sync packet received: {time_s}")
        
        # Update playhead position
        self._playback.set_playhead(time_s)
        
        # 2. Send telemetry immediately
        self._publish_snapshot(time_s, playing=False, advance_frame=True, force_send=True)

    # -------------------- Internal helpers --------------------
    def _publish_snapshot(self, playhead_s: float, playing: bool, *, advance_frame: bool, force_send: bool = False) -> None:
        frame_index = self._telemetry_frame_index
        self._send_snapshot(playing, playhead_s, frame_index, force_send=force_send)
        if advance_frame:
            self._telemetry_frame_index = frame_index + 1

    def _send_snapshot(self, playing: bool, playhead_s: float, frame_index: int, force_send: bool = False) -> None:
        timeline = self._timeline_getter()
        snapshots = self._snapshot_builder(timeline, playhead_s)
        payload = self._payload_builder(snapshots)
        self._telemetry_bridge.update_snapshot(
            playing=playing,
            playhead_ms=int(playhead_s * 1000),
            frame_index=frame_index,
            track_snapshots=payload,
            force_send=force_send,
        )
