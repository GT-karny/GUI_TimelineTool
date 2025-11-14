"""TrackRow widget - 表示トラック1本分のレイアウトをまとめる。"""
from __future__ import annotations

from typing import Optional

from PySide6 import QtCore, QtWidgets

from ..core.timeline import Track
from ..playback.controller import PlaybackController
from .timeline_plot import TimelinePlot


class TrackRow(QtWidgets.QWidget):
    """1トラック分のラベルとタイムラインプロットをまとめた行。"""

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

        self.label = QtWidgets.QLabel(track.name, self)
        self.label.setMinimumWidth(120)
        self.label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)

        self.timeline_plot = TimelinePlot(self)
        self.timeline_plot.set_track(track)
        self.timeline_plot.set_duration(self._duration_s)
        if playback is not None:
            self.timeline_plot.set_playback_controller(playback)

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
