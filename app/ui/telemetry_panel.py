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
        self._session_placeholder: str | None = None

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(8)

        self.chk_enabled = QtWidgets.QCheckBox("Enable UDP telemetry", self)
        layout.addWidget(self.chk_enabled)

        def _make_labeled_widget(label_text: str, widget: QtWidgets.QWidget) -> QtWidgets.QWidget:
            container = QtWidgets.QWidget(self)
            container_layout = QtWidgets.QHBoxLayout(container)
            container_layout.setContentsMargins(0, 0, 0, 0)
            container_layout.setSpacing(4)

            label = QtWidgets.QLabel(label_text, container)
            if hasattr(label, "setBuddy"):
                label.setBuddy(widget)
            container_layout.addWidget(label)
            container_layout.addWidget(widget)
            return container

        self.txt_ip = QtWidgets.QLineEdit(self)
        self.txt_ip.setPlaceholderText("127.0.0.1")
        self.txt_ip.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        layout.addWidget(_make_labeled_widget("IP", self.txt_ip))

        self.spin_port = QtWidgets.QSpinBox(self)
        self.spin_port.setRange(1, 65535)
        self.spin_port.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
        layout.addWidget(_make_labeled_widget("Port", self.spin_port))

        self.spin_rate = QtWidgets.QSpinBox(self)
        self.spin_rate.setRange(1, 240)
        self.spin_rate.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
        layout.addWidget(_make_labeled_widget("Rate (Hz)", self.spin_rate))

        self.txt_session = QtWidgets.QLineEdit(self)
        self.txt_session.setPlaceholderText("Leave blank for auto")
        self.txt_session.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self.txt_session.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        layout.addWidget(_make_labeled_widget("Session ID", self.txt_session))

        # Sync Mode controls
        self.chk_sync = QtWidgets.QCheckBox("Sync Mode", self)
        self.chk_sync.setToolTip("Receive time via UDP and send telemetry immediately")
        layout.addWidget(self.chk_sync)

        self.spin_sync_port = QtWidgets.QSpinBox(self)
        self.spin_sync_port.setRange(1, 65535)
        self.spin_sync_port.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
        layout.addWidget(_make_labeled_widget("Sync Port", self.spin_sync_port))

        layout.addStretch(1)

        self._connect_signals()

    def _connect_signals(self) -> None:
        self.chk_enabled.toggled.connect(self._on_field_changed)
        self.txt_ip.editingFinished.connect(self._on_field_changed)
        self.spin_port.valueChanged.connect(self._on_field_changed)
        self.spin_rate.valueChanged.connect(self._on_field_changed)
        self.txt_session.editingFinished.connect(self._on_field_changed)
        self.chk_sync.toggled.connect(self._on_field_changed)
        self.spin_sync_port.valueChanged.connect(self._on_field_changed)

    def set_settings(
        self,
        settings: TelemetrySettings,
        *,
        session_placeholder: str | None = None,
    ) -> None:
        """Populate UI elements from telemetry settings."""

        self._ui_updating = True
        self._session_placeholder = session_placeholder
        try:
            self.chk_enabled.setChecked(settings.enabled)
            self.txt_ip.setText(settings.ip)
            self.spin_port.setValue(int(settings.port))
            self.spin_rate.setValue(int(settings.rate_hz))
            if settings.session_id:
                self.txt_session.setText(settings.session_id)
            else:
                self.txt_session.clear()
                if session_placeholder:
                    self.txt_session.setPlaceholderText(session_placeholder)
            self.chk_sync.setChecked(settings.sync_enabled)
            self.spin_sync_port.setValue(int(settings.sync_port))
            self._current_debug_log = settings.debug_log
        finally:
            self._ui_updating = False

    def get_settings(self) -> TelemetrySettings:
        """Capture telemetry settings from the UI."""

        session_text = self.txt_session.text().strip()
        session_placeholder = (self._session_placeholder or "").strip()
        return TelemetrySettings(
            enabled=self.chk_enabled.isChecked(),
            ip=self.txt_ip.text().strip() or "127.0.0.1",
            port=int(self.spin_port.value()),
            rate_hz=int(self.spin_rate.value()),
            session_id=session_text or session_placeholder or None,
            sync_enabled=self.chk_sync.isChecked(),
            sync_port=int(self.spin_sync_port.value()),
            debug_log=getattr(self, "_current_debug_log", False),
        )

    def _on_field_changed(self) -> None:
        if self._ui_updating:
            return
        settings = self.get_settings()
        self.settings_changed.emit(settings)
