# ui/toolbar.py
from __future__ import annotations
from PySide6 import QtWidgets, QtCore, QtGui


INTERP_MODE_OPTIONS = [
    ("cubic", "Cubic"),
    ("linear", "Linear"),
    ("step", "Step"),
    ("bezier", "Bezier (Handles)"),
]

INTERP_MODE_LABELS = {value: label for value, label in INTERP_MODE_OPTIONS}


class TimelineToolbar(QtWidgets.QToolBar):
    # ---- 外向きシグナル ----
    sig_interp_changed = QtCore.Signal(str)     # "cubic" | "linear" | "step" | "bezier"
    sig_duration_changed = QtCore.Signal(float) # seconds
    sig_rate_changed = QtCore.Signal(float)     # Hz
    sig_add = QtCore.Signal()
    sig_delete = QtCore.Signal()
    sig_reset = QtCore.Signal()
    sig_export = QtCore.Signal()
    sig_play = QtCore.Signal()
    sig_stop = QtCore.Signal()
    sig_fitx = QtCore.Signal()
    sig_fity = QtCore.Signal()
    sig_loop_toggled = QtCore.Signal(bool)
    sig_seek_start = QtCore.Signal()

    def __init__(self, duration_s: float, sample_rate_hz: float, parent=None):
        super().__init__(parent)

        # --- Widgets ---
        self.mode_combo = QtWidgets.QComboBox()
        for value, label in INTERP_MODE_OPTIONS:
            self.mode_combo.addItem(label, userData=value)

        self.duration = QtWidgets.QDoubleSpinBox()
        self.duration.setRange(0.1, 10000.0)
        self.duration.setDecimals(3)
        self.duration.setValue(duration_s)
        self.duration.setSuffix(" s")

        self.rate = QtWidgets.QDoubleSpinBox()
        self.rate.setRange(1.0, 1000.0)
        self.rate.setDecimals(1)
        self.rate.setValue(sample_rate_hz)
        self.rate.setSuffix(" Hz")

        self.btn_add = QtWidgets.QPushButton("+")
        self.btn_del = QtWidgets.QPushButton("-")
        self.btn_reset = QtWidgets.QPushButton("Reset")
        self.btn_export = QtWidgets.QPushButton("Export CSV")
        self.btn_loop = QtWidgets.QPushButton("Loop")
        self.btn_loop.setCheckable(True)
        self.btn_loop.setToolTip("Loop playback")
        self.btn_loop.setShortcut(QtGui.QKeySequence("L"))
        self.btn_seek_start = QtWidgets.QPushButton("⏮")
        self.btn_seek_start.setToolTip("Move playhead to start")
        self.btn_play = QtWidgets.QPushButton("▶")
        self.btn_stop = QtWidgets.QPushButton("■")
        self.btn_fitx = QtWidgets.QPushButton("|-|")
        self.btn_fity = QtWidgets.QPushButton("工")

        self.btn_add.setToolTip("Add Key @Cursor")
        self.btn_del.setToolTip("Delete Selected")
        self.btn_fitx.setToolTip("Fit X Axis")
        self.btn_fity.setToolTip("Fit Y Axis")

        for b in (self.btn_add, self.btn_del, self.btn_fitx, self.btn_fity):
            b.setFixedSize(30, 24)   # ぴったりサイズに固定

        # --- Layout on toolbar ---
        self.addWidget(QtWidgets.QLabel("Interpolation: "))
        self.addWidget(self.mode_combo)
        self.addSeparator()

        self.addWidget(QtWidgets.QLabel("Duration: "))
        self.addWidget(self.duration)

        self.addWidget(QtWidgets.QLabel("Sample: "))
        self.addWidget(self.rate)
        self.addSeparator()

        for b in (self.btn_add, self.btn_del, self.btn_reset, self.btn_export,
                  self.btn_loop, self.btn_seek_start, self.btn_play, self.btn_stop, self.btn_fitx, self.btn_fity):
            self.addWidget(b)

        # --- Wiring (emit clean signals only) ---
        self.mode_combo.currentIndexChanged.connect(self._emit_interp_changed)
        self.duration.valueChanged.connect(self.sig_duration_changed)
        self.rate.valueChanged.connect(self.sig_rate_changed)
        self.btn_add.clicked.connect(self.sig_add.emit)
        self.btn_del.clicked.connect(self.sig_delete.emit)
        self.btn_reset.clicked.connect(self.sig_reset.emit)
        self.btn_export.clicked.connect(self.sig_export.emit)
        self.btn_loop.toggled.connect(self.sig_loop_toggled.emit)
        self.btn_seek_start.clicked.connect(self.sig_seek_start.emit)
        self.btn_play.clicked.connect(self.sig_play.emit)
        self.btn_stop.clicked.connect(self.sig_stop.emit)
        self.btn_fitx.clicked.connect(self.sig_fitx.emit)
        self.btn_fity.clicked.connect(self.sig_fity.emit)

    # ---- Optional: 外部からの更新用ヘルパ ----
    def set_interp(self, name: str) -> None:
        """'cubic'|'linear'|'step'|'bezier' をUIに反映（signalは出さない）。"""
        i = self.mode_combo.findData(name)
        if i >= 0:
            # note: setCurrentIndexはcurrentTextChangedを発火するので、
            # 外部からのUI同期で signal を抑えたい場合は blockSignals を使う。
            self.mode_combo.blockSignals(True)
            self.mode_combo.setCurrentIndex(i)
            self.mode_combo.blockSignals(False)

    def _emit_interp_changed(self, index: int) -> None:
        mode = self.mode_combo.itemData(index)
        if mode is not None:
            self.sig_interp_changed.emit(str(mode))

    def set_duration(self, seconds: float) -> None:
        self.duration.blockSignals(True)
        self.duration.setValue(float(seconds))
        self.duration.blockSignals(False)

    def set_rate(self, hz: float) -> None:
        self.rate.blockSignals(True)
        self.rate.setValue(float(hz))
        self.rate.blockSignals(False)

    def set_loop(self, enabled: bool) -> None:
        self.btn_loop.blockSignals(True)
        self.btn_loop.setChecked(bool(enabled))
        self.btn_loop.blockSignals(False)
