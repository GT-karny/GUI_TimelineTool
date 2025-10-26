import json
import socket
from typing import Any, Dict

import pytest

from app.net.udp_sender import Endpoint, UdpSenderService
from app.telemetry.assembler import TelemetryAssembler
from app.telemetry.settings import TelemetrySettings, load_settings, save_settings
from app.playback.telemetry_bridge import TelemetryBridge


class DummySettings:
    def __init__(self):
        self.data: Dict[str, Any] = {}

    def value(self, key: str, default: Any = None):
        return self.data.get(key, default)

    def setValue(self, key: str, value: Any) -> None:
        self.data[key] = value

    def remove(self, key: str) -> None:
        self.data.pop(key, None)


def test_telemetry_assembler_builds_expected_payload():
    assembler = TelemetryAssembler(session_id="fixed")
    payload = assembler.build_payload(
        playhead_ms=123,
        frame_index=5,
        track_snapshots=[{"name": "TrackA", "value": 0.5}],
    )
    decoded = json.loads(payload.decode("utf-8"))
    assert decoded == {
        "version": "1.0",
        "session_id": "fixed",
        "timestamp_ms": 123,
        "frame_index": 5,
        "tracks": [{"name": "TrackA", "value": 0.5}],
    }


def test_load_settings_clamps_values():
    qsettings = DummySettings()
    qsettings.setValue("telemetry/enabled", "true")
    qsettings.setValue("telemetry/ip", "192.168.0.10")
    qsettings.setValue("telemetry/port", 70000)
    qsettings.setValue("telemetry/rate_hz", 500)
    result = load_settings(qsettings)
    assert result.enabled is True
    assert result.ip == "192.168.0.10"
    assert result.port == 65535
    assert result.rate_hz == 240


def test_save_settings_removes_session_when_empty():
    qsettings = DummySettings()
    save_settings(qsettings, TelemetrySettings(enabled=True, session_id="abc"))
    assert qsettings.value("telemetry/session_id") == "abc"
    save_settings(qsettings, TelemetrySettings(enabled=True, session_id=None))
    assert "telemetry/session_id" not in qsettings.data


def test_udp_sender_transmits_latest_payload():
    receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    receiver.bind(("127.0.0.1", 0))
    endpoint = Endpoint("127.0.0.1", receiver.getsockname()[1])

    service = UdpSenderService(endpoint)
    service.start()
    try:
        service.submit(b"first")
        service.submit(b"second")
        receiver.settimeout(1.0)
        data, _ = receiver.recvfrom(1024)
        assert data == b"second"
    finally:
        service.stop()
        receiver.close()


def test_telemetry_bridge_sends_only_when_enabled_and_playing():
    receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    receiver.bind(("127.0.0.1", 0))
    port = receiver.getsockname()[1]

    qsettings = DummySettings()
    initial_settings = TelemetrySettings(
        enabled=True,
        ip="127.0.0.1",
        port=port,
        rate_hz=120,
        session_id="session-test",
    )
    save_settings(qsettings, initial_settings)

    bridge = TelemetryBridge(qsettings)
    try:
        receiver.settimeout(0.2)
        bridge.maybe_send_frame(False, 10, 1, [{"name": "Track", "value": 1.0}])
        with pytest.raises(socket.timeout):
            receiver.recvfrom(1024)

        bridge.maybe_send_frame(True, 20, 2, [{"name": "Track", "value": 2.0}])
        receiver.settimeout(1.0)
        data, _ = receiver.recvfrom(2048)
        payload = json.loads(data)
        assert payload["frame_index"] == 2
        assert payload["tracks"][0]["value"] == pytest.approx(2.0)

        bridge.apply_settings(
            TelemetrySettings(
                enabled=False,
                ip="127.0.0.1",
                port=port,
                rate_hz=120,
                session_id="session-test",
            )
        )
        bridge.maybe_send_frame(True, 30, 3, [{"name": "Track", "value": 3.0}])
        receiver.settimeout(0.2)
        with pytest.raises(socket.timeout):
            receiver.recvfrom(1024)
    finally:
        bridge.shutdown()
        receiver.close()
