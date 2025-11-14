"""Telemetry settings panel widget."""
from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from ..telemetry.settings import TelemetrySettings


class TelemetryPanel(QtWidgets.QGroupBox):
    """Widget that exposes telemetry settings editing controls."""

    settings_changed = QtCore.Signal(TelemetrySettings)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__("Telemetry", parent)
        self._ui_updating = False

        layout = QtWidgets.QFormLayout(self)
        layout.setFieldGrowthPolicy(QtWidgets.QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self.chk_enabled = QtWidgets.QCheckBox("Enable UDP telemetry", self)
        layout.addRow(self.chk_enabled)

        self.txt_ip = QtWidgets.QLineEdit(self)
        self.txt_ip.setPlaceholderText("127.0.0.1")
        layout.addRow("IP", self.txt_ip)

        self.spin_port = QtWidgets.QSpinBox(self)
        self.spin_port.setRange(1, 65535)
        layout.addRow("Port", self.spin_port)

        self.spin_rate = QtWidgets.QSpinBox(self)
        self.spin_rate.setRange(1, 240)
        layout.addRow("Rate (Hz)", self.spin_rate)

        self.txt_session = QtWidgets.QLineEdit(self)
        self.txt_session.setPlaceholderText("Leave blank for auto")
        layout.addRow("Session ID", self.txt_session)

        self._connect_signals()

    def _connect_signals(self) -> None:
        self.chk_enabled.toggled.connect(self._on_field_changed)
        self.txt_ip.editingFinished.connect(self._on_field_changed)
        self.spin_port.valueChanged.connect(self._on_field_changed)
        self.spin_rate.valueChanged.connect(self._on_field_changed)
        self.txt_session.editingFinished.connect(self._on_field_changed)

    def set_settings(
        self,
        settings: TelemetrySettings,
        *,
        session_placeholder: str | None = None,
    ) -> None:
        """Populate UI elements from telemetry settings."""

        self._ui_updating = True
        try:
            self.chk_enabled.setChecked(settings.enabled)
            self.txt_ip.setText(settings.ip)
            self.spin_port.setValue(int(settings.port))
            self.spin_rate.setValue(int(settings.rate_hz))
            if settings.session_id:
                self.txt_session.setText(settings.session_id)
            elif session_placeholder:
                self.txt_session.setText(session_placeholder)
            else:
                self.txt_session.clear()
        finally:
            self._ui_updating = False

    def get_settings(self) -> TelemetrySettings:
        """Capture telemetry settings from the UI."""

        session_text = self.txt_session.text().strip()
        return TelemetrySettings(
            enabled=self.chk_enabled.isChecked(),
            ip=self.txt_ip.text().strip() or "127.0.0.1",
            port=int(self.spin_port.value()),
            rate_hz=int(self.spin_rate.value()),
            session_id=session_text or None,
        )

    def _on_field_changed(self) -> None:
        if self._ui_updating:
            return
        settings = self.get_settings()
        self.settings_changed.emit(settings)
