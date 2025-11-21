"""Telemetry settings stored via QSettings."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from PySide6.QtCore import QSettings


@dataclass
class TelemetrySettings:
    enabled: bool = False
    ip: str = "127.0.0.1"
    port: int = 9000
    rate_hz: int = 90
    session_id: Optional[str] = None
    sync_enabled: bool = False
    sync_port: int = 9001
    debug_log: bool = False


def _clamp_port(value: int) -> int:
    return max(1, min(65535, int(value)))


def _clamp_rate(value: int) -> int:
    return max(1, min(240, int(value)))


def _parse_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, str):
        return value.lower() in {"1", "true", "yes", "on"}
    return bool(value)


def load_settings(qsettings: QSettings) -> TelemetrySettings:
    """Load telemetry settings from QSettings."""

    enabled_raw = qsettings.value("telemetry/enabled", False)
    ip = qsettings.value("telemetry/ip", "127.0.0.1")
    port_raw = qsettings.value("telemetry/port", 9000)
    rate_raw = qsettings.value("telemetry/rate_hz", 90)
    session_id = qsettings.value("telemetry/session_id", None)
    sync_enabled_raw = qsettings.value("telemetry/sync_enabled", False)
    sync_port_raw = qsettings.value("telemetry/sync_port", 9001)
    debug_log_raw = qsettings.value("telemetry/debug_log", False)

    try:
        port = _clamp_port(int(port_raw))
    except (TypeError, ValueError):
        port = 9000

    try:
        sync_port = _clamp_port(int(sync_port_raw))
    except (TypeError, ValueError):
        sync_port = 9001

    try:
        rate = _clamp_rate(int(rate_raw))
    except (TypeError, ValueError):
        rate = 90

    if isinstance(ip, str):
        ip_str = ip
    else:
        ip_str = "127.0.0.1"

    if isinstance(session_id, str) and session_id:
        session_id_str: Optional[str] = session_id
    else:
        session_id_str = None

    return TelemetrySettings(
        enabled=_parse_bool(enabled_raw),
        ip=ip_str,
        port=port,
        rate_hz=rate,
        session_id=session_id_str,
        sync_enabled=_parse_bool(sync_enabled_raw),
        sync_port=sync_port,
        debug_log=_parse_bool(debug_log_raw),
    )


def save_settings(qsettings: QSettings, settings: TelemetrySettings) -> None:
    """Persist telemetry settings to QSettings."""

    qsettings.setValue("telemetry/enabled", bool(settings.enabled))
    qsettings.setValue("telemetry/ip", settings.ip)
    qsettings.setValue("telemetry/port", _clamp_port(settings.port))
    qsettings.setValue("telemetry/rate_hz", _clamp_rate(settings.rate_hz))
    if settings.session_id:
        qsettings.setValue("telemetry/session_id", settings.session_id)
    else:
        qsettings.remove("telemetry/session_id")
    
    qsettings.setValue("telemetry/sync_enabled", bool(settings.sync_enabled))
    qsettings.setValue("telemetry/sync_port", _clamp_port(settings.sync_port))
    qsettings.setValue("telemetry/debug_log", bool(settings.debug_log))
