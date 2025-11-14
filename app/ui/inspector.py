# ui/inspector.py
from __future__ import annotations
from typing import Sequence

from PySide6 import QtWidgets, QtCore


class KeyInspector(QtWidgets.QWidget):
    """
    ツールバーの下に置く横並びインスペクタ（左揃え）。
    単一選択: 編集可 / 複数 or 未選択: placeholder "—" を表示。
    """
    sig_time_edited = QtCore.Signal(float)
    sig_value_edited = QtCore.Signal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._updating = False

        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(8, 4, 8, 4)
        lay.setSpacing(8)

        # Track
        self.lbl_track = QtWidgets.QLabel("Track")
        self.track_value = QtWidgets.QLabel("—")

        # Time
        self.lbl_time = QtWidgets.QLabel("Time")
        self.time_spin = QtWidgets.QDoubleSpinBox()
        self.time_spin.setRange(0.0, 1e6)
        self.time_spin.setDecimals(6)
        self.time_spin.setSingleStep(0.01)
        self.time_spin.setSuffix(" s")
        self.time_placeholder = QtWidgets.QLabel("—")
        self.time_placeholder.setEnabled(False)

        # Value
        self.lbl_value = QtWidgets.QLabel("Value")
        self.value_spin = QtWidgets.QDoubleSpinBox()
        self.value_spin.setRange(-1e9, 1e9)
        self.value_spin.setDecimals(6)
        self.value_spin.setSingleStep(0.1)
        self.value_placeholder = QtWidgets.QLabel("—")
        self.value_placeholder.setEnabled(False)

        # Stack (編集可 / placeholder の切替)
        self.time_stack = QtWidgets.QStackedWidget()
        self.time_stack.addWidget(self.time_spin)         # 0
        self.time_stack.addWidget(self.time_placeholder)  # 1

        self.value_stack = QtWidgets.QStackedWidget()
        self.value_stack.addWidget(self.value_spin)       # 0
        self.value_stack.addWidget(self.value_placeholder)# 1

        # 並べる（左揃え）
        lay.addWidget(self.lbl_track)
        lay.addWidget(self.track_value)
        lay.addSpacing(12)
        lay.addWidget(self.lbl_time)
        lay.addWidget(self.time_stack)
        lay.addSpacing(12)
        lay.addWidget(self.lbl_value)
        lay.addWidget(self.value_stack)
        lay.addStretch(1)  # 左寄せにして右は空き

        # signals
        self.time_spin.valueChanged.connect(self._emit_time)
        self.value_spin.valueChanged.connect(self._emit_value)

        self.set_selection_state(False)

        # サイズポリシー調整
        self.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
        self.setMaximumHeight(28)  # インスペクタ全体の最大高さ（お好みで 24〜32px）

        # スピンボックスとプレースホルダの高さを揃える
        h = 24  # お好みで
        for w in (self.track_value, self.time_spin, self.value_spin, self.time_placeholder, self.value_placeholder):
            w.setFixedHeight(h)


    # ---- 外部からの反映 ----
    def set_single_values(self, track_name: str, t: float, v: float):
        self._updating = True
        try:
            self._set_track_label([track_name])
            self.time_spin.setValue(float(max(0.0, t)))
            self.value_spin.setValue(float(v))
            self.set_selection_state(True)
        finally:
            self._updating = False

    def set_no_or_multi(self, track_names: Sequence[str] | None = None):
        self._updating = True
        try:
            self._set_track_label(list(track_names or []))
            self.set_selection_state(False)
        finally:
            self._updating = False

    def set_selection_state(self, has_single: bool):
        self.time_stack.setCurrentIndex(0 if has_single else 1)
        self.value_stack.setCurrentIndex(0 if has_single else 1)
        self.time_spin.setEnabled(has_single)
        self.value_spin.setEnabled(has_single)

    # ---- 内部 ----
    def _set_track_label(self, names: Sequence[str]) -> None:
        if not names:
            text = "—"
        else:
            seen = set()
            ordered = []
            for name in names:
                if name not in seen:
                    ordered.append(name)
                    seen.add(name)
            if len(ordered) == 1:
                text = ordered[0]
            else:
                text = f"Multiple ({len(ordered)})"
        self.track_value.setText(text)

    def _emit_time(self, val: float):
        if not self._updating:
            self.sig_time_edited.emit(float(val))

    def _emit_value(self, val: float):
        if not self._updating:
            self.sig_value_edited.emit(float(val))
