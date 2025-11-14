"""TrackContainer - タイムラインのトラック行を束ねる。"""
from __future__ import annotations

from typing import List, Optional

from PySide6 import QtCore, QtWidgets

from ..core.timeline import Timeline, Track
from ..playback.controller import PlaybackController
from .track_row import TrackRow


class TrackContainer(QtWidgets.QWidget):
    """複数トラックのレイアウトとヘッダー操作をまとめたコンテナ。"""

    request_add_track = QtCore.Signal()
    request_remove_track = QtCore.Signal(str)
    rows_changed = QtCore.Signal()

    def __init__(
        self,
        playback: PlaybackController,
        *,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        super().__init__(parent)

        self._playback = playback
        self._timeline: Optional[Timeline] = None
        self._rows: List[TrackRow] = []

        self._build_ui()

    # ---- public API ----
    def set_timeline(self, timeline: Timeline) -> None:
        self._timeline = timeline
        self._rebuild_rows()

    def update_duration(self, duration_s: float) -> None:
        for row in self._rows:
            row.set_duration(duration_s)

    def refresh_all_rows(self) -> None:
        for row in self._rows:
            row.refresh()

    @property
    def rows(self) -> List[TrackRow]:
        return list(self._rows)

    @property
    def primary_row(self) -> Optional[TrackRow]:
        return self._rows[0] if self._rows else None

    # ---- UI helpers ----
    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        header = QtWidgets.QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(6)

        title = QtWidgets.QLabel("Tracks", self)
        title.setStyleSheet("font-weight: bold;")
        header.addWidget(title)
        header.addStretch(1)

        self.btn_add = QtWidgets.QToolButton(self)
        self.btn_add.setText("+")
        self.btn_add.setToolTip("Add track")
        self.btn_add.clicked.connect(self.request_add_track.emit)
        header.addWidget(self.btn_add)

        self.btn_remove = QtWidgets.QToolButton(self)
        self.btn_remove.setText("-")
        self.btn_remove.setToolTip("Remove last track")
        self.btn_remove.clicked.connect(self._emit_remove_last)
        header.addWidget(self.btn_remove)

        layout.addLayout(header)

        self._rows_layout = QtWidgets.QVBoxLayout()
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout.setSpacing(2)

        layout.addLayout(self._rows_layout)

    def _rebuild_rows(self) -> None:
        if self._timeline is None:
            while self._rows_layout.count():
                self._rows_layout.takeAt(0)
            for row in self._rows:
                row.setParent(None)
                row.deleteLater()
            self._rows.clear()
            self.rows_changed.emit()
            return

        duration = self._timeline.duration_s
        tracks = list(self._timeline.iter_tracks())

        # レイアウト項目を一旦外す
        while self._rows_layout.count():
            self._rows_layout.takeAt(0)

        new_rows: List[TrackRow] = []
        for idx, track in enumerate(tracks):
            if idx < len(self._rows):
                row = self._rows[idx]
                row.set_track(track)
                row.set_duration(duration)
                row.refresh()
            else:
                row = TrackRow(track, playback=self._playback, duration_s=duration, parent=self)
            new_rows.append(row)
            self._rows_layout.addWidget(row)

        # 余剰行を破棄
        for row in self._rows[len(tracks):]:
            row.setParent(None)
            row.deleteLater()

        self._rows = new_rows

        self._link_viewboxes()
        self._update_remove_enabled()
        self.rows_changed.emit()

    def _link_viewboxes(self) -> None:
        if not self._rows:
            return

        base = self._rows[0].timeline_plot.viewbox
        base.setXLink(None)
        for row in self._rows[1:]:
            row.timeline_plot.viewbox.setXLink(base)

    def _emit_remove_last(self) -> None:
        if self._timeline is None:
            return

        tracks = list(self._timeline.iter_tracks())
        if len(tracks) <= 1:
            return

        last: Track = tracks[-1]
        self.request_remove_track.emit(last.track_id)

    def _update_remove_enabled(self) -> None:
        count = len(self._rows)
        self.btn_remove.setEnabled(count > 1)
