"""TrackRow widget - 表示トラック1本分のレイアウトをまとめる。"""
from __future__ import annotations

from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from ..core.timeline import Track, TrackType
from ..playback.controller import PlaybackController
from .timeline_plot import TimelinePlot


class TrackRow(QtWidgets.QWidget):
    """1トラック分のラベルとタイムラインプロットをまとめた行。"""

    activated = QtCore.Signal(object)
    name_edited = QtCore.Signal(str, str)
    label_x_edited = QtCore.Signal(str, str)  # track_id, label_x
    label_y_edited = QtCore.Signal(str, str)  # track_id, label_y
    selection_changed = QtCore.Signal(object, bool)  # row, selected

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
        self._selected = False
        self._last_committed_old_name: Optional[str] = None

        self._syncing_name = False
        self._syncing_label_x = False
        self._syncing_label_y = False

        # チェックボックス（選択用）
        self.checkbox = QtWidgets.QCheckBox(self)
        self.checkbox.setToolTip("Select track for deletion")
        self.checkbox.stateChanged.connect(self._on_checkbox_changed)

        self.name_edit = QtWidgets.QLineEdit(track.name, self)
        self.name_edit.setObjectName("TrackNameEdit")
        self.name_edit.setFrame(False)
        self.name_edit.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        self.name_edit.setMinimumWidth(120)
        self.name_edit.setPlaceholderText("Track name")
        self.name_edit.editingFinished.connect(self._on_name_edit_finished)

        # Vector2Track用のX/Yラベル編集フィールド
        self.label_x_edit: Optional[QtWidgets.QLineEdit] = None
        self.label_y_edit: Optional[QtWidgets.QLineEdit] = None
        is_vector2 = getattr(track, "track_type", TrackType.SCALAR) == TrackType.VECTOR2
        if is_vector2:
            self.label_x_edit = QtWidgets.QLineEdit(track.label_x or "X", self)
            self.label_x_edit.setObjectName("LabelXEdit")
            self.label_x_edit.setFrame(False)
            self.label_x_edit.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
            self.label_x_edit.setMinimumWidth(60)
            self.label_x_edit.setMaximumWidth(80)
            self.label_x_edit.setPlaceholderText("X label")
            self.label_x_edit.editingFinished.connect(self._on_label_x_edit_finished)

            self.label_y_edit = QtWidgets.QLineEdit(track.label_y or "Y", self)
            self.label_y_edit.setObjectName("LabelYEdit")
            self.label_y_edit.setFrame(False)
            self.label_y_edit.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
            self.label_y_edit.setMinimumWidth(60)
            self.label_y_edit.setMaximumWidth(80)
            self.label_y_edit.setPlaceholderText("Y label")
            self.label_y_edit.editingFinished.connect(self._on_label_y_edit_finished)

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
            #TrackRow[selected="true"] {
                background-color: rgba(255, 200, 80, 60);
            }
            """
        )

        # メインレイアウト（横並び）
        main_layout = QtWidgets.QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(8)
        
        # 左側の縦レイアウト（チェックボックス、トラック名、ラベル行）
        left_layout = QtWidgets.QVBoxLayout()
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(4)
        
        # 上段：チェックボックスとトラック名（横並び）
        top_row = QtWidgets.QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(8)
        top_row.addWidget(self.checkbox)
        top_row.addWidget(self.name_edit)
        left_layout.addLayout(top_row)
        
        # 下段：ラベル編集フィールド（Vector2Trackの場合のみ、横並び）
        if is_vector2:
            label_row = QtWidgets.QHBoxLayout()
            label_row.setContentsMargins(0, 0, 0, 0)
            label_row.setSpacing(8)
            if self.label_x_edit is not None:
                label_row.addWidget(self.label_x_edit)
            if self.label_y_edit is not None:
                label_row.addWidget(self.label_y_edit)
            label_row.addStretch()  # 右側を埋める
            left_layout.addLayout(label_row)
        
        # 左側レイアウトをメインレイアウトに追加
        left_widget = QtWidgets.QWidget()
        left_widget.setLayout(left_layout)
        left_widget.setMaximumWidth(300)  # 左側の最大幅を制限
        main_layout.addWidget(left_widget)
        
        # 右側：タイムラインプロット
        main_layout.addWidget(self.timeline_plot, 1)

    # ---- public API ----
    @property
    def track(self) -> Track:
        """Return the associated Track object."""
        return self._track

    def set_track(self, track: Track) -> None:
        """Update the track object and refresh the UI."""
        self._track = track
        self._set_name_text(track.name)
        is_vector2 = getattr(track, "track_type", TrackType.SCALAR) == TrackType.VECTOR2
        
        # レイアウトを取得
        main_layout = self.layout()
        if main_layout is None:
            return
        
        # 左側のウィジェットを取得（最初のウィジェット）
        left_widget = main_layout.itemAt(0).widget() if main_layout.count() > 0 else None
        if left_widget is None:
            return
        
        left_layout = left_widget.layout()
        if left_layout is None:
            return
        
        # Vector2Trackの場合、ラベル編集フィールドが必要
        if is_vector2:
            # ラベル行が既に存在するかチェック
            label_row_exists = False
            if left_layout.count() >= 2:
                # 2番目のアイテムがラベル行かチェック
                item = left_layout.itemAt(1)
                if item and item.layout():
                    label_row_exists = True
            
            if self.label_x_edit is None:
                # ラベル編集フィールドを作成
                self.label_x_edit = QtWidgets.QLineEdit(track.label_x or "X", self)
                self.label_x_edit.setObjectName("LabelXEdit")
                self.label_x_edit.setFrame(False)
                self.label_x_edit.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
                self.label_x_edit.setMinimumWidth(60)
                self.label_x_edit.setMaximumWidth(80)
                self.label_x_edit.setPlaceholderText("X label")
                self.label_x_edit.editingFinished.connect(self._on_label_x_edit_finished)
            
            if self.label_y_edit is None:
                # ラベル編集フィールドを作成
                self.label_y_edit = QtWidgets.QLineEdit(track.label_y or "Y", self)
                self.label_y_edit.setObjectName("LabelYEdit")
                self.label_y_edit.setFrame(False)
                self.label_y_edit.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
                self.label_y_edit.setMinimumWidth(60)
                self.label_y_edit.setMaximumWidth(80)
                self.label_y_edit.setPlaceholderText("Y label")
                self.label_y_edit.editingFinished.connect(self._on_label_y_edit_finished)
            
            # ラベル行が存在しない場合は作成
            if not label_row_exists:
                label_row = QtWidgets.QHBoxLayout()
                label_row.setContentsMargins(0, 0, 0, 0)
                label_row.setSpacing(8)
                if self.label_x_edit is not None:
                    label_row.addWidget(self.label_x_edit)
                if self.label_y_edit is not None:
                    label_row.addWidget(self.label_y_edit)
                label_row.addStretch()
                left_layout.addLayout(label_row)
            
            # ラベル編集フィールドを表示
            if self.label_x_edit is not None:
                self._set_label_x_text(track.label_x or "X")
                self.label_x_edit.show()
            if self.label_y_edit is not None:
                self._set_label_y_text(track.label_y or "Y")
                self.label_y_edit.show()
        else:
            # ScalarTrackの場合、ラベル行を削除
            if left_layout.count() >= 2:
                # 2番目のアイテム（ラベル行）を削除
                item = left_layout.takeAt(1)
                if item:
                    if item.layout():
                        # レイアウト内のウィジェットを削除
                        while item.layout().count():
                            child_item = item.layout().takeAt(0)
                            if child_item and child_item.widget():
                                child_item.widget().setParent(None)
                    elif item.widget():
                        item.widget().setParent(None)
                    del item
            
            # ラベル編集フィールドを非表示
            if self.label_x_edit is not None:
                self.label_x_edit.hide()
            if self.label_y_edit is not None:
                self.label_y_edit.hide()
        
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

    def set_selected(self, selected: bool) -> None:
        """Set the selection state of the row."""
        if self._selected == selected:
            return
        self._selected = bool(selected)
        self.setProperty("selected", self._selected)
        self.checkbox.setChecked(selected)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()
        self.selection_changed.emit(self, selected)

    # ---- Qt events -----------------------------------------------------
    def focusInEvent(self, event: QtGui.QFocusEvent) -> None:  # type: ignore[override]
        self.activated.emit(self)
        super().focusInEvent(event)

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:  # type: ignore[override]
        if event.button() == QtCore.Qt.LeftButton:
            # チェックボックス上でクリックした場合は選択状態をトグル
            if self.checkbox.geometry().contains(event.pos()):
                self.checkbox.setChecked(not self.checkbox.isChecked())
                return
            # それ以外の場合はアクティブ化
            modifiers = event.modifiers()
            if modifiers & QtCore.Qt.ShiftModifier:
                # Shift+クリック: 複数選択（親コンテナで処理）
                self.activated.emit(self)
            elif modifiers & QtCore.Qt.ControlModifier:
                # Ctrl+クリック: トグル選択
                self.set_selected(not self._selected)
            else:
                # 通常クリック: アクティブ化
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

    def _on_checkbox_changed(self, state: int) -> None:
        """チェックボックスの状態変更を処理"""
        self.set_selected(state == QtCore.Qt.CheckState.Checked.value)

    def _set_label_x_text(self, text: str) -> None:
        """Xラベルのテキストを設定"""
        if self.label_x_edit is None:
            return
        if self.label_x_edit.text() == text:
            return
        self._syncing_label_x = True
        self.label_x_edit.setText(text)
        self._syncing_label_x = False

    def _set_label_y_text(self, text: str) -> None:
        """Yラベルのテキストを設定"""
        if self.label_y_edit is None:
            return
        if self.label_y_edit.text() == text:
            return
        self._syncing_label_y = True
        self.label_y_edit.setText(text)
        self._syncing_label_y = False

    def _on_label_x_edit_finished(self) -> None:
        """Xラベル編集完了時の処理"""
        if self._syncing_label_x:
            return
        new_label = self.label_x_edit.text().strip() if self.label_x_edit else ""
        if not new_label:
            new_label = "X"
        if new_label == (self._track.label_x or "X"):
            return
        self._track.label_x = new_label
        self._set_label_x_text(new_label)
        self.label_x_edited.emit(self._track.track_id, new_label)

    def _on_label_y_edit_finished(self) -> None:
        """Yラベル編集完了時の処理"""
        if self._syncing_label_y:
            return
        new_label = self.label_y_edit.text().strip() if self.label_y_edit else ""
        if not new_label:
            new_label = "Y"
        if new_label == (self._track.label_y or "Y"):
            return
        self._track.label_y = new_label
        self._set_label_y_text(new_label)
        self.label_y_edited.emit(self._track.track_id, new_label)
