# ui/main_window.py
from __future__ import annotations

import logging
from typing import Dict, List, Optional, Set, Tuple
from PySide6 import QtWidgets, QtCore
from PySide6.QtGui import QKeySequence, QUndoCommand, QUndoStack
import numpy as np

from ..core.timeline import Timeline, Keyframe, InterpMode, Track
from ..core.interpolation import evaluate
from ..services.export_dialog import export_timeline_csv_via_dialog
from .controllers import ProjectController, TelemetryController
from .track_container import TrackContainer
from .track_row import TrackRow
from .toolbar import TimelineToolbar
from .inspector import KeyInspector  # ★ 追加
from .telemetry_panel import TelemetryPanel

from ..interaction.selection import SelectionManager, SelectedKey
from ..interaction.pos_provider import SingleTrackPosProvider
from ..interaction.key_edit_service import KeyEditService
from ..interaction.mouse_controller import MouseController
from ..playback.controller import PlaybackController
from ..playback.telemetry_bridge import TelemetryBridge


from ..actions.undo_commands import (
    AddKeyCommand,
    AddTrackCommand,
    DeleteKeysCommand,
    RemoveTrackCommand,
    RenameTrackCommand,
    SetKeyTimeCommand,
    SetKeyValueCommand,
)

logger = logging.getLogger(__name__)


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Timeline Editor (modular + inspector)")
        self._base_title = self.windowTitle()
        self.resize(1400, 780)

        self._init_model_state()
        self._init_toolbar()
        self._init_central_widgets()
        self._init_undo_stack()
        self._init_controllers()
        self._wire_signals()
        self._initialize_view_state()

    def _init_model_state(self) -> None:
        # --- Model ---
        self.timeline = Timeline()
        self.sample_rate_hz: float = 90.0
        self._app_settings = QtCore.QSettings("TimelineTool", "TimelineTool")
        self.telemetry_bridge = TelemetryBridge(self._app_settings)
        self.playback = PlaybackController(self.timeline, self._app_settings)

    def _init_toolbar(self) -> None:
        # --- Toolbar ---
        self.toolbar = TimelineToolbar(self.timeline.duration_s, self.sample_rate_hz)
        self.addToolBar(self.toolbar)

    def _init_central_widgets(self) -> None:
        # 中央コンテナ
        central = QtWidgets.QWidget(self)
        vbox = QtWidgets.QVBoxLayout(central)
        vbox.setContentsMargins(4, 4, 4, 4)
        vbox.setSpacing(4)

        # ★ インスペクタをツールバー下に配置
        self.inspector = KeyInspector()
        self.telemetry_panel = TelemetryPanel()

        vbox.addWidget(self.telemetry_panel)
        vbox.addWidget(self.inspector)

        # トラックコンテナ
        self.track_container = TrackContainer(self.playback, parent=self)
        self.track_container.rows_changed.connect(self._on_track_rows_changed)
        vbox.addWidget(self.track_container)

        self.setCentralWidget(central)
        self.setStatusBar(QtWidgets.QStatusBar())

        # モデル→ビュー注入
        self.track_container.set_timeline(self.timeline)
        self._on_track_rows_changed()

    def _init_undo_stack(self) -> None:
        self.undo = QUndoStack(self)
        # 内蔵アクションを作ってメインウィンドウに登録（Ctrl+Z / Ctrl+Y も自動付与）
        self.act_undo = self.undo.createUndoAction(self, "Undo")
        self.act_redo = self.undo.createRedoAction(self, "Redo")
        self.act_undo.setShortcuts(QKeySequence.StandardKey.Undo)
        self.act_redo.setShortcuts(QKeySequence.StandardKey.Redo)
        # 念のためアプリケーションスコープで効くように
        self.act_undo.setShortcutContext(QtCore.Qt.ApplicationShortcut)
        self.act_redo.setShortcutContext(QtCore.Qt.ApplicationShortcut)
        self.addAction(self.act_undo)
        self.addAction(self.act_redo)

        # ついでにUndo/Redoのたびに再描画
        self.undo.indexChanged.connect(self._refresh_view)
        self.undo.indexChanged.connect(self._log_undo_stack_state)

    def _init_controllers(self) -> None:
        self.project_controller = ProjectController(self)
        self.telemetry_controller = TelemetryController(
            playback=self.playback,
            telemetry_bridge=self.telemetry_bridge,
            telemetry_panel=self.telemetry_panel,
            timeline_getter=lambda: self.timeline,
        )
        self._build_menu()

    def _wire_signals(self) -> None:
        # --- Playback controller ---
        self.playback.playhead_changed.connect(self._on_playback_playhead_changed)
        self.playback.playing_changed.connect(self._on_playback_state_changed)
        self.playback.loop_enabled_changed.connect(self.toolbar.set_loop)

        # --- Selection / Mouse 配線 ---
        active_row = self.track_container.active_row
        if active_row is None:
            raise RuntimeError("TrackContainer did not provide an active row")

        self._pos_provider = SingleTrackPosProvider(
            active_row.timeline_plot.plot,
            active_row.track,
            track_id=active_row.track.track_id,
        )
        self.sel = SelectionManager(active_row.timeline_plot.plot.scene(), self._pos_provider)
        self._key_edit = KeyEditService(
            timeline=self.timeline,
            selection=self.sel,
            pos_provider=self._pos_provider,
            push_undo=self.undo.push,
        )
        self.mouse = MouseController(
            plot_widget=active_row.timeline_plot.plot,
            timeline=self.timeline,
            selection=self.sel,
            pos_provider=self._pos_provider,
            on_changed=self._refresh_view,
            set_playhead=self.playback.set_playhead,
            key_edit=self._key_edit,
        )

        # --- Track コンテナ操作 ---
        self.track_container.request_add_track.connect(self._on_request_add_track)
        self.track_container.request_remove_track.connect(self._on_request_remove_track)
        self.track_container.request_rename_track.connect(self._on_request_rename_track)
        self.track_container.active_row_changed.connect(self._on_active_row_changed)

        # Inspector signals -> apply edits
        self.inspector.sig_time_edited.connect(self._on_inspector_time)
        self.inspector.sig_value_edited.connect(self._on_inspector_value)

        # --- Wire toolbar signals ---
        self.toolbar.sig_interp_changed.connect(self._on_interp_changed)
        self.toolbar.sig_duration_changed.connect(self._on_duration_changed)
        self.toolbar.sig_rate_changed.connect(self._on_rate_changed)
        self.toolbar.sig_add.connect(self._on_add_key_at_playhead)
        self.toolbar.sig_delete.connect(self._on_delete_selected)
        self.toolbar.sig_reset.connect(self._on_reset)
        self.toolbar.sig_export.connect(self._on_export_csv)
        self.toolbar.sig_loop_toggled.connect(self._on_loop_toggled)
        self.toolbar.sig_seek_start.connect(self._on_seek_start)
        self.toolbar.sig_play.connect(self._on_play)
        self.toolbar.sig_stop.connect(self._on_stop)
        self.toolbar.sig_fitx.connect(self.plotw.fit_x)
        self.toolbar.sig_fity.connect(lambda: self.plotw.fit_y(0.05))

        self.telemetry_panel.settings_changed.connect(self.telemetry_controller.on_settings_changed)

    def _on_track_rows_changed(self) -> None:
        active = self.track_container.active_row or self.track_container.primary_row
        if active is None:
            return

        self._sync_active_row(active)
        if hasattr(self, "sel"):
            self.sel.retain_tracks(r.track.track_id for r in self.track_container.rows)

    def _on_request_add_track(self) -> None:
        cmd = AddTrackCommand(self.timeline)
        self.undo.push(cmd)
        self._refresh_view()

    def _on_active_row_changed(self, row: Optional[TrackRow]) -> None:
        if row is None:
            return
        self._sync_active_row(row)
        if hasattr(self, "sel"):
            self.sel.retain_tracks(r.track.track_id for r in self.track_container.rows)
            self._refresh_view()

    def _sync_active_row(self, row: TrackRow) -> None:
        self.plotw = row.timeline_plot
        self.plotw.set_track(row.track)
        self.plotw.set_duration(self.timeline.duration_s)
        self.plotw.set_playback_controller(self.playback)

        if hasattr(self, "_pos_provider"):
            self._pos_provider.set_binding(self.plotw.plot, row.track, row.track.track_id)
        if hasattr(self, "sel"):
            self.sel.set_scene(self.plotw.plot.scene())
        if hasattr(self, "mouse"):
            self.mouse.set_plot_widget(self.plotw.plot)
        if hasattr(self, "toolbar"):
            self.toolbar.set_interp(row.track.interp.value)

    def _current_track(self) -> Track:
        row = self.track_container.active_row
        if row is not None:
            return row.track
        return self.timeline.track

    def _on_request_remove_track(self, track_id: str) -> None:
        cmd = RemoveTrackCommand(self.timeline, track_id)
        self.undo.push(cmd)
        self._refresh_view()

    def _on_request_rename_track(self, track_id: str, new_name: str) -> None:
        track = next((t for t in self.timeline.iter_tracks() if t.track_id == track_id), None)
        if track is None:
            return

        old_name = self.track_container.take_pending_rename_old_name(track_id)
        if old_name is None:
            old_name = track.name if track.name != new_name else new_name

        if old_name == new_name:
            return

        cmd = RenameTrackCommand(self.timeline, track_id, new_name, old_name=old_name)
        self.undo.push(cmd)
        self._refresh_view()

    def _initialize_view_state(self) -> None:
        # --- 初期描画・レンジ ---
        self._refresh_view()
        self.plotw.fit_x()
        self.plotw.fit_y(0.15)

        self.project_controller.update_window_title()
        self.telemetry_controller.initialize_panel()

        # 初期プレイヘッドを同期
        self.playback.set_playhead(0.0)
        self.toolbar.set_loop(self.playback.loop_enabled)

    # -------------------- Toolbar handlers --------------------
    def _on_interp_changed(self, name: str):
        track = self._current_track()
        try:
            track.interp = InterpMode(name)
        except ValueError:
            logger.warning("Unknown interpolation mode requested: %s", name)
            return
        if hasattr(self, "toolbar"):
            self.toolbar.set_interp(track.interp.value)
        self._refresh_view()

    def _on_duration_changed(self, seconds: float):
        self.timeline.set_duration(float(seconds))
        self.track_container.update_duration(self.timeline.duration_s)
        self.plotw.fit_x()
        self.playback.clamp_to_duration()
        self._refresh_view()

    def _on_rate_changed(self, hz: float):
        self.sample_rate_hz = float(hz)

    def _on_loop_toggled(self, enabled: bool) -> None:
        self.playback.loop_enabled = bool(enabled)

    def _on_seek_start(self) -> None:
        self.playback.set_playhead(0.0)

    def _on_add_key_at_playhead(self):
        t = float(self.plotw.playhead.value())
        # 仕様：補間値を初期値に
        track = self._current_track()
        track_id = track.track_id
        v = float(evaluate(track, np.array([t]))[0])
        cmd = AddKeyCommand(self.timeline, track_id, t, v)
        self.undo.push(cmd)
        # 直近追加キーを選択（redoで追加されるので参照は cmd 内の k）
        kf = cmd.k
        if kf is not None:
            self.sel.set_single(track_id, id(kf))
        self._refresh_view()

    def _on_delete_selected(self):
        grouped = self._selected_keys_by_track()
        if not grouped:
            return

        root = QUndoCommand("Delete Selected Keys")
        for track_id, keys in grouped.items():
            if not keys:
                continue
            DeleteKeysCommand(self.timeline, track_id, keys, parent=root)

        if root.childCount() == 0:
            return

        self.undo.push(root)
        self.sel.clear()
        self._refresh_view()

    def _on_reset(self):
        track = self._current_track()
        track.keys.clear()
        track.keys.append(Keyframe(0.0, 0.0))
        track.keys.append(Keyframe(self.timeline.duration_s, 0.0))
        self.sel.clear()
        self._refresh_view()

    def _on_export_csv(self):
        export_timeline_csv_via_dialog(self, self.timeline, self.sample_rate_hz)

    def _on_play(self):
        self.playback.play()

    def _on_stop(self):
        self.playback.stop()

    # -------------------- Inspector handlers --------------------
    def _on_inspector_time(self, t_new: float):
        pairs = self._resolved_selection()
        if len(pairs) != 1:
            return
        track, k = pairs[0]
        t_new = float(max(0.0, t_new))
        if abs(k.t - t_new) < 1e-12:
            return
        self.undo.push(SetKeyTimeCommand(self.timeline, track.track_id, k, old_t=k.t, new_t=t_new))
        self._refresh_view()

    def _on_inspector_value(self, v_new: float):
        pairs = self._resolved_selection()
        if len(pairs) != 1:
            return
        _track, k = pairs[0]
        v_new = float(v_new)
        if abs(k.v - v_new) < 1e-12:
            return
        self.undo.push(SetKeyValueCommand(k, old_v=k.v, new_v=v_new))
        self._refresh_view()

    # -------------------- Playback callbacks --------------------
    def _on_playback_playhead_changed(self, playhead_s: float, playing: bool) -> None:
        self.plotw.set_playhead(playhead_s)
        self.telemetry_controller.on_playback_playhead_changed(playhead_s, playing)

    def _on_playback_state_changed(self, playing: bool) -> None:
        self.telemetry_controller.on_playback_state_changed(playing)

    # -------------------- View refresh + inspector sync --------------------
    def _refresh_view(self):
        self.track_container.set_timeline(self.timeline)

        resolved = self._resolved_selection()
        valid_selected = {SelectedKey(track.track_id, id(key)) for track, key in resolved}
        current_key_selected = {sel for sel in self.sel.selected if sel.is_key}
        if valid_selected != current_key_selected:
            others = {sel for sel in self.sel.selected if not sel.is_key}
            self.sel.selected = valid_selected | others
            resolved = self._resolved_selection()

        selection_map: Dict[str, Set[SelectedKey]] = {}
        for sel in self.sel.selected:
            selection_map.setdefault(sel.track_id, set()).add(sel)

        for row in self.track_container.rows:
            track = row.track
            selected = selection_map.get(track.track_id, set())
            row.timeline_plot.update_points(selected)

        if len(resolved) == 1:
            track, key = resolved[0]
            self.inspector.set_single_values(track.name, key.t, key.v)
        else:
            names = [track.name for track, _ in resolved]
            self.inspector.set_no_or_multi(names)

    # -------------------- Helpers --------------------
    def _resolved_selection(self) -> List[Tuple[Track, Keyframe]]:
        track_map = {track.track_id: track for track in self.timeline.iter_tracks()}
        resolved: List[Tuple[Track, Keyframe]] = []
        invalid: Set[SelectedKey] = set()
        for sel in set(self.sel.selected):
            track = track_map.get(sel.track_id)
            if track is None:
                invalid.add(sel)
                continue
            if not sel.is_key:
                key = next((k for k in track.keys if id(k) == sel.key_id), None)
                if key is None:
                    invalid.add(sel)
                    continue
                handle = None
                if sel.component == "handle_in":
                    handle = key.handle_in
                elif sel.component == "handle_out":
                    handle = key.handle_out
                if handle is None or id(handle) != sel.item_id:
                    invalid.add(sel)
                continue
            key = next((k for k in track.keys if id(k) == sel.key_id), None)
            if key is None:
                invalid.add(sel)
                continue
            resolved.append((track, key))
        if invalid:
            self.sel.selected -= invalid
        return resolved

    def _selected_keys_by_track(self) -> Dict[str, List[Keyframe]]:
        grouped: Dict[str, List[Keyframe]] = {}
        for track, key in self._resolved_selection():
            grouped.setdefault(track.track_id, []).append(key)
        return grouped

    def _log_undo_stack_state(self, _: int) -> None:
        logger.debug(
            "Undo stack changed: index=%d count=%d clean=%s",
            self.undo.index(),
            self.undo.count(),
            self.undo.isClean(),
        )

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self.telemetry_controller.shutdown()
        super().closeEvent(event)

    # -------------------- File menu helpers --------------------
    def _build_menu(self) -> None:
        menu = self.menuBar().addMenu("&File")

        self.act_new = menu.addAction("New File")
        self.act_new.setShortcut(QKeySequence.StandardKey.New)
        self.act_new.setShortcutContext(QtCore.Qt.ApplicationShortcut)
        self.act_new.triggered.connect(self.project_controller.on_new_file)

        self.act_load = menu.addAction("Load File")
        self.act_load.setShortcut(QKeySequence.StandardKey.Open)
        self.act_load.setShortcutContext(QtCore.Qt.ApplicationShortcut)
        self.act_load.triggered.connect(self.project_controller.on_load_file)

        menu.addSeparator()

        self.act_save = menu.addAction("Save File")
        self.act_save.setShortcut(QKeySequence.StandardKey.Save)
        self.act_save.setShortcutContext(QtCore.Qt.ApplicationShortcut)
        self.act_save.triggered.connect(self.project_controller.on_save_file)

        self.act_save_as = menu.addAction("Save File as name")
        self.act_save_as.setShortcut(QKeySequence("Ctrl+Shift+S"))
        self.act_save_as.setShortcutContext(QtCore.Qt.ApplicationShortcut)
        self.act_save_as.triggered.connect(self.project_controller.on_save_file_as)

        for act in (self.act_new, self.act_load, self.act_save, self.act_save_as):
            self.addAction(act)
