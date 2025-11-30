"""TrackContainer - タイムラインのトラック行を束ねる。"""
from __future__ import annotations

from typing import Dict, List, Optional

from PySide6 import QtCore, QtGui, QtWidgets

from ..core.timeline import Timeline, Track
from ..playback.controller import PlaybackController
from .track_row import TrackRow


class TrackContainer(QtWidgets.QWidget):
    """複数トラックのレイアウトとヘッダー操作をまとめたコンテナ。"""

    request_add_track = QtCore.Signal()
    request_remove_track = QtCore.Signal(str)
    request_remove_selected_tracks = QtCore.Signal()
    request_rename_track = QtCore.Signal(str, str)
    request_set_label_x = QtCore.Signal(str, str)  # track_id, label_x
    request_set_label_y = QtCore.Signal(str, str)  # track_id, label_y
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
        self._track_height: int = 180
        self._selected_track_ids: set[str] = set()
        self._last_selected_row: Optional[TrackRow] = None

        self._build_ui()

    # ---- public API ----
    def set_timeline(self, timeline: Timeline) -> None:
        previous_timeline = self._timeline
        self._timeline = timeline

        # Check if structure changed
        current_ids = [row.track.track_id for row in self._rows]
        new_ids = [t.track_id for t in timeline.iter_tracks()]

        if current_ids == new_ids and previous_timeline is timeline:
            self.refresh_all_rows()
            return

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

    @property
    def selected_tracks(self) -> List[str]:
        """選択中のトラックIDリストを取得"""
        return list(self._selected_track_ids)

    def set_track_selected(self, track_id: str, selected: bool) -> None:
        """トラックの選択状態を設定"""
        for row in self._rows:
            if row.track.track_id == track_id:
                row.set_selected(selected)
                break

    def clear_selection(self) -> None:
        """選択をクリア"""
        for row in self._rows:
            if row._selected:
                row.set_selected(False)
        self._selected_track_ids.clear()
        self._last_selected_row = None

    # ---- UI helpers ----
    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        layout.addLayout(self._setup_header())
        layout.addWidget(self._setup_scroll_area())

    def _setup_header(self) -> QtWidgets.QHBoxLayout:
        header = QtWidgets.QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(6)

        title = QtWidgets.QLabel("Tracks", self)
        title.setStyleSheet("font-weight: bold;")
        header.addWidget(title)
        header.addStretch(1)

        self.slider_height = QtWidgets.QSlider(QtCore.Qt.Horizontal, self)
        self.slider_height.setRange(60, 600)
        self.slider_height.setValue(self._track_height)
        self.slider_height.setFixedWidth(80)
        self.slider_height.setToolTip("Track Height")
        self.slider_height.valueChanged.connect(self._on_height_slider_changed)
        header.addWidget(self.slider_height)

        self.btn_add = QtWidgets.QToolButton(self)
        self.btn_add.setText("+")
        self.btn_add.setToolTip("Add track")
        self.btn_add.clicked.connect(self.request_add_track.emit)
        header.addWidget(self.btn_add)

        self.btn_remove = QtWidgets.QToolButton(self)
        self.btn_remove.setText("-")
        self.btn_remove.setToolTip("Remove selected tracks (or last track if none selected)")
        self.btn_remove.clicked.connect(self._on_remove_clicked)
        header.addWidget(self.btn_remove)

        # Deleteキーのショートカット
        self._delete_shortcut = QtGui.QShortcut(QtGui.QKeySequence.Delete, self)
        self._delete_shortcut.activated.connect(self._on_delete_key_pressed)

        return header

    def _setup_scroll_area(self) -> QtWidgets.QScrollArea:
        # Scroll Area setup
        self._scroll_area = QtWidgets.QScrollArea(self)
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setFrameShape(QtWidgets.QFrame.NoFrame)

        # Container widget for the rows
        self._scroll_content = QtWidgets.QWidget()
        self._rows_layout = QtWidgets.QVBoxLayout(self._scroll_content)
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout.setSpacing(2)
        self._rows_layout.addStretch(1)  # Push tracks to top

        self._scroll_area.setWidget(self._scroll_content)
        return self._scroll_area

    def _rebuild_rows(self) -> None:
        self._pending_rename_old_names.clear()
        # 選択状態をクリア（トラックが再構築されるため）
        self._selected_track_ids.clear()
        self._last_selected_row = None

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

        # レイアウト項目を一旦外す (stretch含む)
        while self._rows_layout.count():
            item = self._rows_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
            # SpacerItems (stretch) are just removed and discarded

        new_rows: List[TrackRow] = []
        for idx, track in enumerate(tracks):
            is_new = False
            if idx < len(self._rows):
                row = self._rows[idx]
                row.set_track(track)
                row.set_duration(duration)
                row.refresh()
            else:
                row = TrackRow(track, playback=self._playback, duration_s=duration, parent=self)
                row.activated.connect(self._on_row_activated)
                row.selection_changed.connect(self._on_row_selection_changed)
                row.label_x_edited.connect(self._on_row_label_x_edited)
                row.label_y_edited.connect(self._on_row_label_y_edited)
                is_new = True
            
            row.setFixedHeight(self._track_height)
            self._ensure_row_connections(row, is_new=is_new)
            new_rows.append(row)
            self._rows_layout.addWidget(row)

        # Push tracks to top
        self._rows_layout.addStretch(1)

        # 余剰行を破棄
        for row in self._rows[len(tracks):]:
            row.setParent(None)
            row.deleteLater()

        self._rows = new_rows

        self._restore_active_row()

        self._link_viewboxes()
        self._update_remove_enabled()
        self.rows_changed.emit()

    def _ensure_row_connections(self, row: TrackRow, is_new: bool) -> None:
        if not is_new:
            try:
                row.name_edited.disconnect(self._on_row_name_edited)
                row.selection_changed.disconnect(self._on_row_selection_changed)
                row.label_x_edited.disconnect(self._on_row_label_x_edited)
                row.label_y_edited.disconnect(self._on_row_label_y_edited)
            except (TypeError, RuntimeError):
                pass
        row.name_edited.connect(self._on_row_name_edited)
        row.selection_changed.connect(self._on_row_selection_changed)
        row.label_x_edited.connect(self._on_row_label_x_edited)
        row.label_y_edited.connect(self._on_row_label_y_edited)

    def _link_viewboxes(self) -> None:
        if not self._rows:
            return

        base = self._rows[0].timeline_plot.viewbox
        base.setXLink(None)
        for row in self._rows[1:]:
            row.timeline_plot.viewbox.setXLink(base)

    def _on_remove_clicked(self) -> None:
        """削除ボタンがクリックされた時の処理"""
        if self._timeline is None:
            return

        tracks = list(self._timeline.iter_tracks())
        if len(tracks) <= 1:
            return

        # 選択中のトラックがある場合はそれらを削除
        if self._selected_track_ids:
            self.request_remove_selected_tracks.emit()
        else:
            # 選択がない場合は最後のトラックを削除（従来の動作）
            last: Track = tracks[-1]
            self.request_remove_track.emit(last.track_id)

    def _on_delete_key_pressed(self) -> None:
        """Deleteキーが押された時の処理"""
        if self._selected_track_ids:
            self.request_remove_selected_tracks.emit()

    def _update_remove_enabled(self) -> None:
        count = len(self._rows)
        self.btn_remove.setEnabled(count > 1)

    def _on_row_activated(self, row: TrackRow) -> None:
        """行がアクティブ化された時の処理（Shift+クリックで複数選択）"""
        modifiers = QtWidgets.QApplication.keyboardModifiers()
        if modifiers & QtCore.Qt.ShiftModifier and self._last_selected_row is not None:
            # Shift+クリック: 最後に選択した行から現在の行までを選択
            start_idx = self._rows.index(self._last_selected_row)
            end_idx = self._rows.index(row)
            if start_idx > end_idx:
                start_idx, end_idx = end_idx, start_idx
            for i in range(start_idx, end_idx + 1):
                self.set_track_selected(self._rows[i].track.track_id, True)
        else:
            # 通常クリック: アクティブ化のみ
            self.set_active_row(row)
            self._last_selected_row = row

    def _on_row_selection_changed(self, row: TrackRow, selected: bool) -> None:
        """行の選択状態が変更された時の処理"""
        track_id = row.track.track_id
        if selected:
            self._selected_track_ids.add(track_id)
            self._last_selected_row = row
        else:
            self._selected_track_ids.discard(track_id)
            if self._last_selected_row is row:
                self._last_selected_row = None

    def _on_row_label_x_edited(self, track_id: str, label_x: str) -> None:
        """Xラベルが編集された時の処理"""
        self.request_set_label_x.emit(track_id, label_x)

    def _on_row_label_y_edited(self, track_id: str, label_y: str) -> None:
        """Yラベルが編集された時の処理"""
        self.request_set_label_y.emit(track_id, label_y)

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

    def _on_height_slider_changed(self, value: int) -> None:
        self._track_height = value
        for row in self._rows:
            row.setFixedHeight(value)
        # Force layout to recalculate
        self._rows_layout.invalidate()
