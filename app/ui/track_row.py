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
    name_edited = QtCore.Signal(str, str)

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
        self._last_committed_old_name: Optional[str] = None

        self._syncing_name = False

        self.name_edit = QtWidgets.QLineEdit(track.name, self)
        self.name_edit.setObjectName("TrackNameEdit")
        self.name_edit.setFrame(False)
        self.name_edit.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        self.name_edit.setMinimumWidth(120)
        self.name_edit.setPlaceholderText("Track name")
        self.name_edit.editingFinished.connect(self._on_name_edit_finished)

        self.timeline_plot = TimelinePlot(self)
        self.timeline_plot.set_track(track)
        self.timeline_plot.set_duration(self._duration_s)
        if playback is not None:
            self.timeline_plot.set_playback_controller(playback)

        # Install event filter to capture clicks on the plot
        self.timeline_plot.plot.scene().installEventFilter(self)

        self.setObjectName("TrackRow")
        self.setProperty("active", False)
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.setStyleSheet(
            """
            #TrackRow[active="true"] {
                border: 1px solid rgba(60, 160, 255, 200);
                background-color: rgba(60, 160, 255, 40);
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
        layout.addWidget(self.name_edit)
        layout.addWidget(self.timeline_plot, 1)

    # ---- public API ----
    @property
    def track(self) -> Track:
        """Return the associated Track object."""
        return self._track

    def set_track(self, track: Track) -> None:
        """Update the track object and refresh the UI."""
        self._track = track
        self._set_name_text(track.name)
        self.timeline_plot.set_track(track)

    def set_duration(self, duration_s: float) -> None:
        """Update the duration of the timeline plot."""
        self._duration_s = float(duration_s)
        self.timeline_plot.set_duration(duration_s)

    def set_playback_controller(self, playback: Optional[PlaybackController]) -> None:
        """Set the playback controller for the timeline plot."""
        self.timeline_plot.set_playback_controller(playback)

    def refresh(self) -> None:
        """Refresh the track name and curve from the model."""
        self._set_name_text(self._track.name)
        self.timeline_plot.update_curve()

    def set_active(self, active: bool) -> None:
        """Set the active state of the row (visual highlighting)."""
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

    def mouseDoubleClickEvent(self, event: QtGui.QMouseEvent) -> None:  # type: ignore[override]
        if event.button() == QtCore.Qt.LeftButton:
            self.name_edit.setFocus(QtCore.Qt.FocusReason.MouseFocusReason)
            self.name_edit.selectAll()
        super().mouseDoubleClickEvent(event)

    def eventFilter(self, watched: QtCore.QObject, event: QtCore.QEvent) -> bool:
        if watched is self.timeline_plot.plot.scene():
            if event.type() == QtCore.QEvent.GraphicsSceneMousePress:
                if event.button() == QtCore.Qt.LeftButton:
                    self.activated.emit(self)
        return super().eventFilter(watched, event)

    # ---- helpers ----------------------------------------------------------
    def _set_name_text(self, text: str) -> None:
        if self.name_edit.text() == text:
            return
        self._syncing_name = True
        self.name_edit.setText(text)
        self._syncing_name = False

    def _on_name_edit_finished(self) -> None:
        if self._syncing_name:
            return
        self._commit_name_edit()

    def _commit_name_edit(self) -> None:
        new_name = self.name_edit.text().strip()
        if not new_name:
            self._set_name_text(self._track.name)
            return

        if new_name == self._track.name:
            self._set_name_text(self._track.name)
            return

        self._last_committed_old_name = self._track.name
        self._track.name = new_name
        self._set_name_text(new_name)
        self.name_edited.emit(self._track.track_id, new_name)

    def consume_last_committed_old_name(self) -> Optional[str]:
        old = self._last_committed_old_name
        self._last_committed_old_name = None
        return old
