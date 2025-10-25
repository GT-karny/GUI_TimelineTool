# ui/main_window.py
from __future__ import annotations
from typing import Set, List, Optional
from PySide6 import QtWidgets, QtCore
from PySide6.QtGui import QUndoStack
import numpy as np

from ..core.timeline import Timeline, Keyframe, InterpMode
from ..core.interpolation import evaluate
from ..io.csv_exporter import export_csv
from .timeline_plot import TimelinePlot
from .toolbar import TimelineToolbar
from .inspector import KeyInspector  # ★ 追加

from ..interaction.selection import SelectionManager
from ..interaction.pos_provider import SingleTrackPosProvider
from ..interaction.mouse_controller import MouseController


from ..actions.undo_commands import (
    AddKeyCommand, DeleteKeysCommand, MoveKeyCommand,
    SetKeyTimeCommand, SetKeyValueCommand
)

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Timeline Editor (modular + inspector)")
        self.resize(1400, 780)

        # --- Model ---
        self.timeline = Timeline()
        self.sample_rate_hz: float = 90.0

        # --- Toolbar ---
        self.toolbar = TimelineToolbar(self.timeline.duration_s, self.sample_rate_hz)
        self.addToolBar(self.toolbar)

        # --- Plot (center) ---
        self.plotw = TimelinePlot(self)

        # 中央コンテナ
        central = QtWidgets.QWidget(self)
        vbox = QtWidgets.QVBoxLayout(central)
        vbox.setContentsMargins(4, 4, 4, 4)
        vbox.setSpacing(4)

        # ★ インスペクタをツールバー下に配置
        self.inspector = KeyInspector()
        vbox.addWidget(self.inspector)

        # プロットを下に
        vbox.addWidget(self.plotw)

        self.setCentralWidget(central)
        self.setStatusBar(QtWidgets.QStatusBar())

        # モデル→ビュー注入
        self.plotw.set_timeline(self.timeline)

        self.undo = QUndoStack(self)
        # 内蔵アクションを作ってメインウィンドウに登録（Ctrl+Z / Ctrl+Y も自動付与）
        self.act_undo = self.undo.createUndoAction(self, "Undo")
        self.act_redo = self.undo.createRedoAction(self, "Redo")
        # 念のためアプリケーションスコープで効くように
        self.act_undo.setShortcutContext(QtCore.Qt.ApplicationShortcut)
        self.act_redo.setShortcutContext(QtCore.Qt.ApplicationShortcut)
        self.addAction(self.act_undo)
        self.addAction(self.act_redo)

        # ついでにUndo/Redoのたびに再描画
        self.undo.indexChanged.connect(self._refresh_view)
        self.undo.indexChanged.connect(lambda _: print(
            f"[UNDO DEBUG] index={self.undo.index()} / count={self.undo.count()} / clean={self.undo.isClean()}"
        ))


        # --- Selection / Mouse 配線 ---
        self._pos_provider = SingleTrackPosProvider(self.plotw.plot, self.timeline.track, track_id=0)
        self.sel = SelectionManager(self.plotw.plot.scene(), self._pos_provider)
        self.mouse = MouseController(
            plot_widget=self.plotw.plot,
            timeline=self.timeline,
            selection=self.sel,
            pos_provider=self._pos_provider,
            on_changed=self._refresh_view,
            set_playhead=self.plotw.set_playhead,
            commit_drag=lambda key, before, after: self.undo.push(
                MoveKeyCommand(self.timeline, key, before, after)
            ),
            # ▼ 追加：右クリック/ダブルクリックの Add/Delete を Undo に積む
            add_key_cb=lambda t, v: (lambda cmd: (self.undo.push(cmd), cmd.k)[1])(AddKeyCommand(self.timeline, t, v)),
            delete_key_cb=lambda key: self.undo.push(DeleteKeysCommand(self.timeline, [key])),
        )


        # Inspector signals -> apply edits
        self.inspector.sig_time_edited.connect(self._on_inspector_time)
        self.inspector.sig_value_edited.connect(self._on_inspector_value)

        # --- Playback（暫定: 内蔵タイマー） ---
        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._on_tick)
        self._t0: Optional[QtCore.QTime] = None
        self._play_fps = 60

        # --- 初期描画・レンジ ---
        self._refresh_view()
        self.plotw.fit_x()
        self.plotw.fit_y(0.15)

        # --- Wire toolbar signals ---
        self.toolbar.sig_interp_changed.connect(self._on_interp_changed)
        self.toolbar.sig_duration_changed.connect(self._on_duration_changed)
        self.toolbar.sig_rate_changed.connect(self._on_rate_changed)
        self.toolbar.sig_add.connect(self._on_add_key_at_playhead)
        self.toolbar.sig_delete.connect(self._on_delete_selected)
        self.toolbar.sig_reset.connect(self._on_reset)
        self.toolbar.sig_export.connect(self._on_export_csv)
        self.toolbar.sig_play.connect(self._on_play)
        self.toolbar.sig_stop.connect(self._on_stop)
        self.toolbar.sig_fitx.connect(self.plotw.fit_x)
        self.toolbar.sig_fity.connect(lambda: self.plotw.fit_y(0.05))



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
        self.plotw.fit_x()
        self._refresh_view()

    def _on_rate_changed(self, hz: float):
        self.sample_rate_hz = float(hz)

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
        self._t0 = QtCore.QTime.currentTime()
        self._timer.start(int(1000 / self._play_fps))

    def _on_stop(self):
        self._timer.stop()

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

    # -------------------- Playback tick（暫定） --------------------
    def _on_tick(self):
        if self._t0 is None:
            return
        elapsed = self._t0.msecsTo(QtCore.QTime.currentTime()) / 1000.0
        t = elapsed % max(1e-6, self.timeline.duration_s)
        self.plotw.set_playhead(t)

    # -------------------- View refresh + inspector sync --------------------
    def _refresh_view(self):
        ks = self.timeline.track.sorted()
        self.plotw.update_curve()

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
