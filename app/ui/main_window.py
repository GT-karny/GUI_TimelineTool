# ui/main_window.py
from __future__ import annotations
from typing import Set, List, Optional
from PySide6 import QtWidgets, QtCore, QtGui
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
from ..core.history import TimelineHistory


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Timeline Editor (modular + inspector)")
        self.resize(1400, 780)

        # --- Model ---
        self.timeline = Timeline()
        self.sample_rate_hz: float = 90.0
        self.history = TimelineHistory(self.timeline)
        self._history_dirty = False

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

        # --- Selection / Mouse 配線 ---
        self._pos_provider = SingleTrackPosProvider(self.plotw.plot, self.timeline.track, track_id=0)
        self.sel = SelectionManager(self.plotw.plot.scene(), self._pos_provider)
        self.mouse = MouseController(
            plot_widget=self.plotw.plot,
            timeline=self.timeline,
            selection=self.sel,
            pos_provider=self._pos_provider,
            on_timeline_preview=self._on_timeline_preview,
            on_timeline_changed=self._on_timeline_changed,
            on_selection_changed=self._on_selection_changed,
            set_playhead=self.plotw.set_playhead,
        )


        # Inspector signals -> apply edits
        self.inspector.sig_time_edited.connect(self._on_inspector_time)
        self.inspector.sig_value_edited.connect(self._on_inspector_value)

        # --- Playback（暫定: 内蔵タイマー） ---
        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._on_tick)
        self._t0: Optional[QtCore.QTime] = None
        self._play_fps = 60

        # --- Shortcuts ---
        self._init_shortcuts()

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
        target = {
            "cubic": InterpMode.CUBIC,
            "linear": InterpMode.LINEAR,
            "step": InterpMode.STEP,
        }[name]
        if self.timeline.track.interp == target:
            return
        self.timeline.track.interp = target
        self._record_timeline_change()

    def _on_duration_changed(self, seconds: float):
        seconds = float(seconds)
        if abs(self.timeline.duration_s - seconds) < 1e-9:
            return
        self.timeline.set_duration(seconds)
        self.plotw.fit_x()
        self._record_timeline_change()

    def _on_rate_changed(self, hz: float):
        self.sample_rate_hz = float(hz)

    def _on_add_key_at_playhead(self):
        t = float(self.plotw.playhead.value())
        v = float(evaluate(self.timeline.track, np.array([t]))[0])
        kf = Keyframe(float(max(0.0, t)), v)
        self.timeline.track.keys.append(kf)
        self.timeline.track.clamp_times()
        self.sel.set_single(0, id(kf))
        self._record_timeline_change()

    def _on_delete_selected(self):
        if not self.sel.selected:
            return
        key_ids = {kid for (tid, kid) in self.sel.selected if tid == 0}
        changed = False
        if key_ids:
            before = len(self.timeline.track.keys)
            self.timeline.track.keys = [k for k in self.timeline.track.keys if id(k) not in key_ids]
            changed = len(self.timeline.track.keys) != before
        self.sel.clear()
        if changed:
            self._record_timeline_change()
        else:
            self._refresh_view()

    def _on_reset(self):
        self.timeline.track.keys.clear()
        self.timeline.track.keys.append(Keyframe(0.0, 0.0))
        self.timeline.track.keys.append(Keyframe(self.timeline.duration_s, 0.0))
        self.sel.clear()
        self._record_timeline_change()

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
        """インスペクタから時刻編集。単一選択なら1件、複数選択なら全件に適用。"""
        key_list = self._selected_keys()
        if not key_list:
            return
        t_new = float(max(0.0, t_new))
        if all(abs(k.t - t_new) < 1e-9 for k in key_list):
            return
        if len(key_list) == 1:
            key_list[0].t = t_new
        else:
            # 複数選択：全て同じ t に（要件に合わせてオフセット維持に変えることも可）
            for k in key_list:
                k.t = t_new
        self.timeline.track.clamp_times()
        self._record_timeline_change()

    def _on_inspector_value(self, v_new: float):
        """インスペクタから値編集。単一/複数選択ともに値を適用。"""
        key_list = self._selected_keys()
        if not key_list:
            return
        v_new = float(v_new)
        if all(abs(k.v - v_new) < 1e-9 for k in key_list):
            return
        for k in key_list:
            k.v = v_new
        self._record_timeline_change()

    # -------------------- Playback tick（暫定） --------------------
    def _on_tick(self):
        if self._t0 is None:
            return
        elapsed = self._t0.msecsTo(QtCore.QTime.currentTime()) / 1000.0
        t = elapsed % max(1e-6, self.timeline.duration_s)
        self.plotw.set_playhead(t)

    # -------------------- View refresh + inspector sync --------------------
    def _refresh_view(self):
        if getattr(self, "history", None) is not None and self._history_dirty:
            self.history.push()
            self._history_dirty = False

        ks = self.timeline.track.sorted()
        self.plotw.update_curve()

        selected_key_ids: Set[int] = {kid for (tid, kid) in self.sel.selected if tid == 0}
        self.plotw.update_points(ks, selected_key_ids)

        # --- toolbar sync ---
        self.toolbar.set_interp(self.timeline.track.interp.value)
        self.toolbar.set_duration(self.timeline.duration_s)

        # --- inspector sync ---
        selected_keys = [k for k in ks if id(k) in selected_key_ids]
        if len(selected_keys) == 1:
            k = selected_keys[0]
            self.inspector.set_single_values(k.t, k.v)
        else:
            self.inspector.set_no_or_multi()

        self._update_history_actions()

    # -------------------- Helpers --------------------
    def _selected_keys(self) -> List[Keyframe]:
        ids = {kid for (tid, kid) in self.sel.selected if tid == 0}
        return [k for k in self.timeline.track.sorted() if id(k) in ids]

    def _record_timeline_change(self) -> None:
        self._history_dirty = True
        self._refresh_view()

    def _on_timeline_preview(self) -> None:
        # インタラクティブ操作中の再描画（履歴追加なし）
        was_dirty = self._history_dirty
        self._history_dirty = False
        self._refresh_view()
        self._history_dirty = was_dirty

    def _on_timeline_changed(self) -> None:
        self._record_timeline_change()

    def _on_selection_changed(self) -> None:
        self._refresh_view()

    def _init_shortcuts(self) -> None:
        self._undo_action = QtGui.QAction("Undo", self)
        self._undo_action.setShortcuts([QtGui.QKeySequence.Undo])
        self._undo_action.triggered.connect(self._on_undo)
        self.addAction(self._undo_action)

        self._redo_action = QtGui.QAction("Redo", self)
        self._redo_action.setShortcuts([QtGui.QKeySequence.Redo, QtGui.QKeySequence("Ctrl+Y")])
        self._redo_action.triggered.connect(self._on_redo)
        self.addAction(self._redo_action)

        self._delete_action = QtGui.QAction("Delete Keys", self)
        self._delete_action.setShortcuts([QtGui.QKeySequence.Delete, QtGui.QKeySequence("Backspace")])
        self._delete_action.triggered.connect(self._on_delete_selected)
        self.addAction(self._delete_action)

        self._update_history_actions()

    def _on_undo(self) -> None:
        if self.history.undo():
            self.sel.clear()
            self._refresh_view()

    def _on_redo(self) -> None:
        if self.history.redo():
            self.sel.clear()
            self._refresh_view()

    def _update_history_actions(self) -> None:
        if not hasattr(self, "_undo_action"):
            return
        self._undo_action.setEnabled(self.history.can_undo())
        self._redo_action.setEnabled(self.history.can_redo())
