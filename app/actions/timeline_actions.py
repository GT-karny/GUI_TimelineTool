# actions/timeline_actions.py
from __future__ import annotations
from typing import Set, Iterable, Tuple, Optional
import numpy as np
from PySide6 import QtWidgets

from ..core.timeline import Timeline, Keyframe
from ..core.interpolation import evaluate
from ..io.csv_exporter import export_csv


class TimelineActions:
    """
    タイムライン編集の純ロジック層。
    - 追加/削除/リセット
    - CSVエクスポート
    - （拡張用）キー移動・一括移動のユーティリティ
    UI再描画は呼び出し側で行う想定。
    """

    def __init__(self, timeline: Timeline, sample_rate_getter=lambda: 90.0):
        self.timeline = timeline
        self._get_rate = sample_rate_getter  # 外部から現在のサンプルレートを取得する関数

    # ---------------- 基本操作 ----------------
    def add_key_at(self, t: float) -> Keyframe:
        """時刻 t にキーを1つ追加。初期値は現行カーブ値。"""
        t = float(max(0.0, t))
        v = float(evaluate(self.timeline.track, np.array([t]))[0])
        kf = Keyframe(t, v)
        self.timeline.track.keys.append(kf)
        self.timeline.track.clamp_times()
        return kf

    def delete_by_ids(self, key_ids: Set[int]) -> int:
        """id(key) の集合で削除。削除数を返す。"""
        if not key_ids:
            return 0
        before = len(self.timeline.track.keys)
        self.timeline.track.keys = [k for k in self.timeline.track.keys if id(k) not in key_ids]
        return before - len(self.timeline.track.keys)

    def reset_two_points(self) -> None:
        """0s=0 と duration=0 の2点に初期化。"""
        dur = self.timeline.duration_s
        self.timeline.track.keys.clear()
        self.timeline.track.keys += [Keyframe(0.0, 0.0), Keyframe(dur, 0.0)]
        self.timeline.track.clamp_times()

    # ---------------- 編集ユーティリティ（任意） ----------------
    def move_key(self, key_obj: Keyframe, dt: float = 0.0, dv: float = 0.0) -> None:
        """単一キーの移動（値は相対）。"""
        key_obj.t = float(max(0.0, key_obj.t + dt))
        key_obj.v = float(key_obj.v + dv)
        self.timeline.track.clamp_times()

    def move_keys_bulk(self, keys: Iterable[Keyframe], dt: float = 0.0, dv: float = 0.0) -> None:
        """複数キーの一括移動（相対）。"""
        dt = float(dt); dv = float(dv)
        for k in keys:
            k.t = float(max(0.0, k.t + dt))
            k.v = float(k.v + dv)
        self.timeline.track.clamp_times()

    # ---------------- エクスポート ----------------
    def export_csv(self, path: str) -> bool:
        """パス指定でCSV出力。成功/失敗を返す。"""
        if not path:
            return False
        export_csv(path, self.timeline, float(self._get_rate()))
        return True

    def export_csv_dialog(self, parent: Optional[QtWidgets.QWidget]) -> bool:
        """保存ダイアログを出してCSV出力。"""
        path, _ = QtWidgets.QFileDialog.getSaveFileName(parent, "Export CSV", "timeline.csv", "CSV Files (*.csv)")
        if not path:
            return False
        ok = self.export_csv(path)
        if ok:
            QtWidgets.QMessageBox.information(parent, "Export", f"Exported to:\n{path}")
        return ok
