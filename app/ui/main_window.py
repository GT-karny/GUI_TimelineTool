# ui/main_window.py
from __future__ import annotations

import logging
from pathlib import Path
from typing import Set, List, Optional
from PySide6 import QtWidgets, QtCore
from PySide6.QtGui import QKeySequence, QUndoStack
import numpy as np

from ..core.timeline import Timeline, Keyframe, InterpMode
from ..core.interpolation import evaluate
from ..io.csv_exporter import export_csv
from ..io.project_io import save_project, load_project
from .track_container import TrackContainer
from .toolbar import TimelineToolbar
from .inspector import KeyInspector  # ★ 追加
from .telemetry_panel import TelemetryPanel

from ..interaction.selection import SelectionManager
from ..interaction.pos_provider import SingleTrackPosProvider
from ..interaction.mouse_controller import MouseController
from ..playback.controller import PlaybackController
from ..playback.telemetry_bridge import TelemetryBridge
from ..telemetry.settings import TelemetrySettings


from ..actions.undo_commands import (
    AddKeyCommand, DeleteKeysCommand, MoveKeyCommand,
    SetKeyTimeCommand, SetKeyValueCommand
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
        self._wire_signals()
        self._initialize_view_state()

    def _init_model_state(self) -> None:
        # --- Model ---
        self.timeline = Timeline()
        self.sample_rate_hz: float = 90.0
        self._current_project_path: Optional[Path] = None
        self._app_settings = QtCore.QSettings("TimelineTool", "TimelineTool")
        self.telemetry_bridge = TelemetryBridge(self._app_settings)
        self._telemetry_frame_index = 0
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

        self._build_menu()

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

    def _wire_signals(self) -> None:
        # --- Playback controller ---
        self.playback.playhead_changed.connect(self._on_playback_playhead_changed)
        self.playback.playing_changed.connect(self._on_playback_state_changed)
        self.playback.loop_enabled_changed.connect(self.toolbar.set_loop)

        # --- Selection / Mouse 配線 ---
        self._pos_provider = SingleTrackPosProvider(self.plotw.plot, self.timeline.track, track_id=0)
        self.sel = SelectionManager(self.plotw.plot.scene(), self._pos_provider)
        self.mouse = MouseController(
            plot_widget=self.plotw.plot,
            timeline=self.timeline,
            selection=self.sel,
            pos_provider=self._pos_provider,
            on_changed=self._refresh_view,
            set_playhead=self.playback.set_playhead,
            commit_drag=lambda key, before, after: self.undo.push(
                MoveKeyCommand(self.timeline, key, before, after)
            ),
            # ▼ 追加：右クリック/ダブルクリックの Add/Delete を Undo に積む
            add_key_cb=lambda t, v: (lambda cmd: (self.undo.push(cmd), cmd.k)[1])(AddKeyCommand(self.timeline, t, v)),
            delete_key_cb=lambda key: self.undo.push(DeleteKeysCommand(self.timeline, [key])),
        )

        # --- Track コンテナ操作 ---
        self.track_container.request_add_track.connect(self._on_request_add_track)
        self.track_container.request_remove_track.connect(self._on_request_remove_track)

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

        self.telemetry_panel.settings_changed.connect(self._on_telemetry_settings_changed)

    def _on_track_rows_changed(self) -> None:
        primary = self.track_container.primary_row
        if primary is None:
            return

        plot = primary.timeline_plot
        replaced = getattr(self, "plotw", None) is not plot
        self.plotw = plot
        self.plotw.set_track(self.timeline.track)
        self.plotw.set_duration(self.timeline.duration_s)
        self.plotw.set_playback_controller(self.playback)

        if hasattr(self, "_pos_provider"):
            self._pos_provider.track = self.timeline.track
            self._pos_provider.vb = self.plotw.plot.plotItem.vb
        if hasattr(self, "mouse") and replaced:
            try:
                self.mouse.plot.scene().removeEventFilter(self.mouse)
            except Exception:
                pass
            self.mouse.plot = self.plotw.plot
            self.mouse.plot.scene().installEventFilter(self.mouse)

    def _on_request_add_track(self) -> None:
        self.timeline.add_track()
        self.track_container.set_timeline(self.timeline)
        self._refresh_view()

    def _on_request_remove_track(self, track_id: str) -> None:
        if not self.timeline.remove_track(track_id):
            return
        self.track_container.set_timeline(self.timeline)
        self._refresh_view()

    def _initialize_view_state(self) -> None:
        # --- 初期描画・レンジ ---
        self._refresh_view()
        self.plotw.fit_x()
        self.plotw.fit_y(0.15)

        self._update_window_title()
        self.telemetry_panel.set_settings(
            self.telemetry_bridge.settings,
            session_placeholder=self.telemetry_bridge.assembler.session_id,
        )

        # 初期プレイヘッドを同期
        self.playback.set_playhead(0.0)
        self.toolbar.set_loop(self.playback.loop_enabled)

    # -------------------- Toolbar handlers --------------------
    def _on_interp_changed(self, name: str):
        self.timeline.track.interp = {
            "cubic": InterpMode.CUBIC,
            "linear": InterpMode.LINEAR,
            "step": InterpMode.STEP,
        }[name]
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
        v = float(evaluate(self.timeline.track, np.array([t]))[0])
        cmd = AddKeyCommand(self.timeline, t, v)
        self.undo.push(cmd)
        # 直近追加キーを選択（redoで追加されるので参照は cmd 内の k）
        kf = cmd.k
        if kf is not None:
            self.sel.set_single(0, id(kf))
        self._refresh_view()

    def _on_delete_selected(self):
        key_ids = {kid for (tid, kid) in self.sel.selected if tid == 0}
        if not key_ids:
            return
        targets = [k for k in self.timeline.track.keys if id(k) in key_ids]
        if not targets:
            return
        self.undo.push(DeleteKeysCommand(self.timeline, targets))
        self.sel.clear()
        self._refresh_view()

    def _on_reset(self):
        self.timeline.track.keys.clear()
        self.timeline.track.keys.append(Keyframe(0.0, 0.0))
        self.timeline.track.keys.append(Keyframe(self.timeline.duration_s, 0.0))
        self.sel.clear()
        self._refresh_view()

    def _on_export_csv(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Export CSV", "timeline.csv", "CSV Files (*.csv)")
        if not path:
            return
        export_csv(path, self.timeline, self.sample_rate_hz)
        QtWidgets.QMessageBox.information(self, "Export", f"Exported to:\n{path}")

    def _on_play(self):
        self.playback.play()

    def _on_stop(self):
        self.playback.stop()

    # -------------------- Inspector handlers --------------------
    def _on_inspector_time(self, t_new: float):
        keys = self._selected_keys()
        if len(keys) != 1:
            return
        k = keys[0]
        t_new = float(max(0.0, t_new))
        if abs(k.t - t_new) < 1e-12:
            return
        self.undo.push(SetKeyTimeCommand(self.timeline, k, old_t=k.t, new_t=t_new))
        self._refresh_view()

    def _on_inspector_value(self, v_new: float):
        keys = self._selected_keys()
        if len(keys) != 1:
            return
        k = keys[0]
        v_new = float(v_new)
        if abs(k.v - v_new) < 1e-12:
            return
        self.undo.push(SetKeyValueCommand(k, old_v=k.v, new_v=v_new))
        self._refresh_view()

    # -------------------- Playback callbacks --------------------
    def _on_playback_playhead_changed(self, playhead_s: float, playing: bool) -> None:
        self.plotw.set_playhead(playhead_s)
        self._publish_telemetry_snapshot(playhead_s, playing, advance_frame=playing)

    def _on_playback_state_changed(self, playing: bool) -> None:
        if playing:
            self._telemetry_frame_index = 0
        self._publish_telemetry_snapshot(self.playback.playhead, playing, advance_frame=False)

    # -------------------- View refresh + inspector sync --------------------
    def _refresh_view(self):
        ks = self.timeline.track.sorted()
        self.track_container.refresh_all_rows()

        selected_key_ids: Set[int] = {kid for (tid, kid) in self.sel.selected if tid == 0}
        self.plotw.update_points(ks, selected_key_ids)

        # --- inspector sync ---
        selected_keys = [k for k in ks if id(k) in selected_key_ids]
        if len(selected_keys) == 1:
            k = selected_keys[0]
            self.inspector.set_single_values(k.t, k.v)
        else:
            self.inspector.set_no_or_multi()

    # -------------------- Helpers --------------------
    def _selected_keys(self) -> List[Keyframe]:
        ids = {kid for (tid, kid) in self.sel.selected if tid == 0}
        return [k for k in self.timeline.track.sorted() if id(k) in ids]

    def _on_telemetry_settings_changed(self, settings: TelemetrySettings) -> None:
        self.telemetry_bridge.apply_settings(settings)
        self.telemetry_panel.set_settings(
            self.telemetry_bridge.settings,
            session_placeholder=self.telemetry_bridge.assembler.session_id,
        )

    def _publish_telemetry_snapshot(self, playhead_s: float, playing: bool, *, advance_frame: bool) -> None:
        frame_index = self._telemetry_frame_index
        self._send_telemetry_frame(playing, playhead_s, frame_index)
        if advance_frame:
            self._telemetry_frame_index = frame_index + 1

    def _send_telemetry_frame(self, playing: bool, playhead_s: float, frame_index: int) -> None:
        track = self.timeline.track
        values = evaluate(track, np.array([playhead_s], dtype=float))
        snapshots = [{"name": track.name, "value": float(values[0])}]
        self.telemetry_bridge.update_snapshot(
            playing=playing,
            playhead_ms=int(playhead_s * 1000),
            frame_index=frame_index,
            track_snapshots=snapshots,
        )

    def _log_undo_stack_state(self, _: int) -> None:
        logger.debug(
            "Undo stack changed: index=%d count=%d clean=%s",
            self.undo.index(),
            self.undo.count(),
            self.undo.isClean(),
        )

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self.telemetry_bridge.shutdown()
        super().closeEvent(event)

    # -------------------- File menu helpers --------------------
    def _build_menu(self) -> None:
        menu = self.menuBar().addMenu("&File")

        self.act_new = menu.addAction("New File")
        self.act_new.setShortcut(QKeySequence.StandardKey.New)
        self.act_new.setShortcutContext(QtCore.Qt.ApplicationShortcut)
        self.act_new.triggered.connect(self._on_new_file)

        self.act_load = menu.addAction("Load File")
        self.act_load.setShortcut(QKeySequence.StandardKey.Open)
        self.act_load.setShortcutContext(QtCore.Qt.ApplicationShortcut)
        self.act_load.triggered.connect(self._on_load_file)

        menu.addSeparator()

        self.act_save = menu.addAction("Save File")
        self.act_save.setShortcut(QKeySequence.StandardKey.Save)
        self.act_save.setShortcutContext(QtCore.Qt.ApplicationShortcut)
        self.act_save.triggered.connect(self._on_save_file)

        self.act_save_as = menu.addAction("Save File as name")
        self.act_save_as.setShortcut(QKeySequence("Ctrl+Shift+S"))
        self.act_save_as.setShortcutContext(QtCore.Qt.ApplicationShortcut)
        self.act_save_as.triggered.connect(self._on_save_file_as)

        for act in (self.act_new, self.act_load, self.act_save, self.act_save_as):
            self.addAction(act)

    def _apply_project(self, tl: Timeline, *, sample_rate: Optional[float] = None,
                       path: Optional[Path] = None) -> None:
        self.timeline = tl
        if sample_rate is not None:
            self.sample_rate_hz = float(sample_rate)

        self.track_container.set_timeline(self.timeline)
        self.track_container.update_duration(self.timeline.duration_s)
        self._on_track_rows_changed()
        self.playback.set_timeline(self.timeline)
        self._pos_provider.track = self.timeline.track
        self.mouse.timeline = self.timeline
        self.sel.clear()

        self.undo.clear()
        self.undo.setClean()

        self.toolbar.set_duration(self.timeline.duration_s)
        self.toolbar.set_interp(self.timeline.track.interp.value)
        self.toolbar.set_rate(self.sample_rate_hz)

        self.playback.set_playhead(0.0)
        self.plotw.fit_x()
        self.plotw.fit_y(0.15)
        self._refresh_view()

        self._current_project_path = path
        self._update_window_title()

    def _update_window_title(self) -> None:
        if self._current_project_path is None:
            suffix = "Untitled"
        else:
            suffix = self._current_project_path.name
        self.setWindowTitle(f"{self._base_title} - {suffix}")

    def _on_new_file(self) -> None:
        self._apply_project(Timeline(), sample_rate=90.0, path=None)
        self.statusBar().showMessage("Started new project", 3000)

    def _on_load_file(self) -> None:
        path_str, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Load Timeline Project",
            str(self._current_project_path or ""),
            "Timeline Project (*.json);;All Files (*)",
        )
        if not path_str:
            return

        path = Path(path_str)
        try:
            tl, sample_rate = load_project(path)
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Load Failed", f"{exc}")
            return

        self._apply_project(tl, sample_rate=sample_rate, path=path)
        self.statusBar().showMessage(f"Loaded project: {path}", 3000)

    def _save_to_path(self, path: Path) -> bool:
        try:
            save_project(path, self.timeline, self.sample_rate_hz)
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Save Failed", f"{exc}")
            return False

        self._current_project_path = path
        self.undo.setClean()
        self._update_window_title()
        self.statusBar().showMessage(f"Saved project: {path}", 3000)
        return True

    def _on_save_file(self) -> None:
        if self._current_project_path is None:
            self._on_save_file_as()
            return
        self._save_to_path(self._current_project_path)

    def _on_save_file_as(self) -> None:
        start_dir = self._current_project_path.parent if self._current_project_path else Path.cwd()
        default_name = self._current_project_path.name if self._current_project_path else "timeline.json"
        path_str, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Save Timeline Project",
            str(start_dir / default_name),
            "Timeline Project (*.json);;All Files (*)",
        )
        if not path_str:
            return
        self._save_to_path(Path(path_str))
