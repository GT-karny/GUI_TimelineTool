"""TrackRow widget - 表示トラック1本分のレイアウトをまとめる。"""
from __future__ import annotations

from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from ..core.timeline import Track
from ..playback.controller import PlaybackController
from .timeline_plot import TimelinePlot


class TrackRow(QtWidgets.QWidget):
    """1トラック分のラベルとタイムラインプロットをまとめた行。"""

    activated = QtCore.Signal(object)

    def __init__(
        self,
        track: Track,
        *,
        playback: Optional[PlaybackController] = None,
        duration_s: float = 10.0,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        super().__init__(parent)

        self._track = track
        self._duration_s = float(duration_s)
        self._active = False

        self.label = QtWidgets.QLabel(track.name, self)
        self.label.setMinimumWidth(120)
        self.label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)

        self.timeline_plot = TimelinePlot(self)
        self.timeline_plot.set_track(track)
        self.timeline_plot.set_duration(self._duration_s)
        if playback is not None:
            self.timeline_plot.set_playback_controller(playback)

        self.setObjectName("TrackRow")
        self.setProperty("active", False)
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.setStyleSheet(
            """
            #TrackRow[active="true"] {
                border: 1px solid rgba(0, 120, 215, 180);
                background-color: rgba(0, 120, 215, 30);
                border-radius: 4px;
            }
            #TrackRow[active="false"] {
                border: 1px solid transparent;
                background-color: transparent;
            }
            """
        )

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self.label)
        layout.addWidget(self.timeline_plot, 1)

    # ---- public API ----
    @property
    def track(self) -> Track:
        return self._track

    def set_track(self, track: Track) -> None:
        self._track = track
        self.label.setText(track.name)
        self.timeline_plot.set_track(track)

    def set_duration(self, duration_s: float) -> None:
        self._duration_s = float(duration_s)
        self.timeline_plot.set_duration(duration_s)

    def set_playback_controller(self, playback: Optional[PlaybackController]) -> None:
        self.timeline_plot.set_playback_controller(playback)

    def refresh(self) -> None:
        """トラックの最新状態を反映。"""
        self.label.setText(self._track.name)
        self.timeline_plot.update_curve()

    def set_active(self, active: bool) -> None:
        if self._active == active:
            return
        self._active = bool(active)
        self.setProperty("active", self._active)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    # ---- Qt events -----------------------------------------------------
    def focusInEvent(self, event: QtGui.QFocusEvent) -> None:  # type: ignore[override]
        self.activated.emit(self)
        super().focusInEvent(event)

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:  # type: ignore[override]
        if event.button() == QtCore.Qt.LeftButton:
            self.activated.emit(self)
        super().mousePressEvent(event)
