"""TrackContainer - タイムラインのトラック行を束ねる。"""
from __future__ import annotations

from typing import Dict, List, Optional

from PySide6 import QtCore, QtWidgets

from ..core.timeline import Timeline, Track
from ..playback.controller import PlaybackController
from .track_row import TrackRow


class TrackContainer(QtWidgets.QWidget):
    """複数トラックのレイアウトとヘッダー操作をまとめたコンテナ。"""

    request_add_track = QtCore.Signal()
    request_remove_track = QtCore.Signal(str)
    request_rename_track = QtCore.Signal(str, str)
    rows_changed = QtCore.Signal()
    active_row_changed = QtCore.Signal(object)

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
        self._active_row: Optional[TrackRow] = None
        self._active_track_id: Optional[str] = None
        self._pending_rename_old_names: Dict[str, Optional[str]] = {}

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

    @property
    def active_row(self) -> Optional[TrackRow]:
        return self._active_row

    def set_active_row(self, row: Optional[TrackRow]) -> None:
        if row is not None and row not in self._rows:
            return
        if row is self._active_row:
            return

        if self._active_row is not None:
            self._active_row.set_active(False)

        self._active_row = row
        self._active_track_id = row.track.track_id if row is not None else None

        if row is not None:
            row.set_active(True)
            row.setFocus(QtCore.Qt.FocusReason.OtherFocusReason)

        self.active_row_changed.emit(row)

    def set_active_track(self, track_id: str) -> bool:
        for row in self._rows:
            if row.track.track_id == track_id:
                self.set_active_row(row)
                return True
        return False

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
        self._pending_rename_old_names.clear()

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
                row.activated.connect(self._on_row_activated)
            self._ensure_row_connections(row)
            new_rows.append(row)
            self._rows_layout.addWidget(row)

        # 余剰行を破棄
        for row in self._rows[len(tracks):]:
            row.setParent(None)
            row.deleteLater()

        self._rows = new_rows

        self._restore_active_row()

        self._link_viewboxes()
        self._update_remove_enabled()
        self.rows_changed.emit()

    def _ensure_row_connections(self, row: TrackRow) -> None:
        try:
            row.name_edited.disconnect(self._on_row_name_edited)
        except (TypeError, RuntimeError):
            pass
        row.name_edited.connect(self._on_row_name_edited)

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

    def _on_row_activated(self, row: TrackRow) -> None:
        self.set_active_row(row)

    def _on_row_name_edited(self, track_id: str, name: str) -> None:
        for row in self._rows:
            if row.track.track_id == track_id:
                old_name = row.consume_last_committed_old_name()
                if old_name is not None:
                    self._pending_rename_old_names[track_id] = old_name
                break
        self.request_rename_track.emit(track_id, name)

    def take_pending_rename_old_name(self, track_id: str) -> Optional[str]:
        return self._pending_rename_old_names.pop(track_id, None)

    def _restore_active_row(self) -> None:
        if not self._rows:
            self.set_active_row(None)
            return

        if self._active_track_id:
            for row in self._rows:
                if row.track.track_id == self._active_track_id:
                    self.set_active_row(row)
                    break
            else:
                self.set_active_row(self._rows[0])
        else:
            self.set_active_row(self._rows[0])
