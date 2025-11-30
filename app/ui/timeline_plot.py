# ui/timeline_plot.py
from __future__ import annotations
from typing import Optional, Set
from PySide6 import QtWidgets, QtGui, QtCore
import pyqtgraph as pg
import numpy as np

from ..core.timeline import Track, Keyframe, InterpMode, TrackType
from ..core.interpolation import evaluate, evaluate_x, evaluate_y
from ..playback.controller import PlaybackController
from ..interaction.selection import SelectedKey


class TimelinePlot(QtWidgets.QWidget):
    """
    タイムラインの描画専任コンポーネント。
    - 曲線・キー点・プレイヘッド表示
    - X/Yレンジの明示制御（自動レンジは無効）
    - UIイベントや編集ロジックは持たない（別モジュールに委譲）
    """

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)

        # モデル参照（外部から set_track で注入）
        self._track: Optional[Track] = None
        self._duration_s: float = 10.0
        self._playback: Optional[PlaybackController] = None

        # ---- Plot 構築 ----
        self.plot = pg.PlotWidget(background="#2b2b2b")
        self.plot.showGrid(x=True, y=True, alpha=0.3)
        self.plot.setLabel("bottom", "Time (s)")
        self.plot.setLabel("left", "Value")

        # AutoRange は完全停止（勝手に動かさない）
        self.plot.plotItem.vb.enableAutoRange(x=False, y=False)

        # 曲線・点・プレイヘッド
        self.curve_item = self.plot.plot([], [], pen=pg.mkPen(200, 200, 200, 255, width=2))
        # Vector2Track用のX/Yカーブ
        self.curve_item_x = self.plot.plot([], [], pen=pg.mkPen(255, 100, 100, 255, width=2))
        self.curve_item_y = self.plot.plot([], [], pen=pg.mkPen(100, 100, 255, 255, width=2))
        self.handle_lines = pg.PlotDataItem(
            [],
            [],
            pen=pg.mkPen(150, 150, 150, 150, width=1),
        )
        self.plot.addItem(self.handle_lines)
        self.handle_points = pg.ScatterPlotItem(size=8)
        self.handle_points.setZValue(2)
        self.plot.addItem(self.handle_points)
        self.points = pg.ScatterPlotItem(size=10)
        self.points.setZValue(1)
        self.plot.addItem(self.points)
        # Vector2Track用のX/Yキーポイント
        self.points_x = pg.ScatterPlotItem(size=10)
        self.points_x.setZValue(1)
        self.plot.addItem(self.points_x)
        self.points_y = pg.ScatterPlotItem(size=10)
        self.points_y.setZValue(1)
        self.plot.addItem(self.points_y)

        self.playhead = pg.InfiniteLine(
            pos=0.0, angle=90, movable=False, pen=pg.mkPen(255, 50, 50, 200)
        )
        self.plot.addItem(self.playhead)

        # レイアウト
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.plot)

    # ---- 基本API ----
    def set_track(self, track: Optional[Track]) -> None:
        """描画対象の Track を注入し、初期描画を行う。"""
        self._track = track
        self.update_curve()
        self.update_points()

    def set_duration(self, duration_s: float) -> None:
        """トラックの時間範囲を設定する。"""
        self._duration_s = max(0.001, float(duration_s))

    def set_playback_controller(self, playback: Optional[PlaybackController]) -> None:
        """プレイバック制御と連動させる。None で切断。"""
        if self._playback is playback:
            return

        if self._playback is not None:
            self._playback.remove_playhead_listener(self._on_playback_playhead)

        self._playback = playback

        if playback is not None:
            playback.add_playhead_listener(self._on_playback_playhead)

    def set_playhead(self, t: float) -> None:
        """プレイヘッド位置を秒で設定。"""
        self.playhead.setValue(float(max(0.0, t)))

    def update_curve(self) -> None:
        """曲線（補間結果）を再描画。"""
        if self._track is None:
            self.curve_item.setData([], [])
            self.curve_item_x.setData([], [])
            self.curve_item_y.setData([], [])
            return

        ks = self._track.sorted()
        tmax = max(self._duration_s, max((k.t for k in ks), default=0.0))
        dense_t = np.linspace(0.0, max(1e-3, tmax), 1200)
        
        if getattr(self._track, "track_type", TrackType.SCALAR) == TrackType.VECTOR2:
            # Vector2Track: XとYの2つのカーブを表示
            dense_vx = evaluate_x(self._track, dense_t)
            dense_vy = evaluate_y(self._track, dense_t)
            self.curve_item.setData([], [])  # スカラーカーブは非表示
            self.curve_item_x.setData(dense_t, dense_vx)
            self.curve_item_y.setData(dense_t, dense_vy)
        else:
            # ScalarTrack: 通常のカーブを表示
            dense_v = evaluate(self._track, dense_t)
            self.curve_item.setData(dense_t, dense_v)
            self.curve_item_x.setData([], [])  # Vector2カーブは非表示
            self.curve_item_y.setData([], [])

    def update_points(self, selected: Set[SelectedKey] | None = None) -> None:
        """キー点およびハンドルを再描画。選択点は強調表示。"""

        if selected is None:
            selected = set()

        if self._track is None:
            self.points.setData([])
            self.points_x.setData([])
            self.points_y.setData([])
            self.handle_points.setData([])
            self.handle_lines.setData([], [])
            return

        keys = self._track.sorted()
        selected_key_ids = {sel.item_id for sel in selected if sel.component == "key"}
        selected_handle_ids = {
            sel.item_id
            for sel in selected
            if sel.component != "key" and sel.item_id is not None
        }

        is_vector2 = getattr(self._track, "track_type", TrackType.SCALAR) == TrackType.VECTOR2
        
        if is_vector2:
            # Vector2Track: キーポイントは0の位置に表示（タイミングを示すため）
            # XとYのカーブは通常通り表示されるが、キーポイントは時間軸上で0の位置
            key_spots = []
            for k in keys:
                key_id = id(k)
                is_sel = key_id in selected_key_ids
                
                # キーポイントは0の位置に表示（タイミングを表す）
                key_spots.append(
                    {
                        "pos": (k.t, 0.0),
                        "data": key_id,
                        "brush": pg.mkBrush(255, 160, 0, 220)
                        if is_sel
                        else pg.mkBrush(200, 200, 200, 180),
                        "size": 12 if is_sel else 10,
                        "pen": pg.mkPen(180, 100, 0, 220)
                        if is_sel
                        else pg.mkPen(150, 150, 150, 200),
                    }
                )
            self.points.setData(key_spots)  # タイミングを表す点を0の位置に表示
            self.points_x.setData([])  # X/Yの個別ポイントは非表示
            self.points_y.setData([])
        else:
            # ScalarTrack: 通常のキーポイントを表示
            key_spots = []
            for k in keys:
                key_id = id(k)
                is_sel = key_id in selected_key_ids
                key_spots.append(
                    {
                        "pos": (k.t, k.v),
                        "data": key_id,
                        "brush": pg.mkBrush(255, 160, 0, 220)
                        if is_sel
                        else pg.mkBrush(40, 120, 255, 180),
                        "size": 12 if is_sel else 10,
                        "pen": pg.mkPen(180, 100, 0, 220)
                        if is_sel
                        else pg.mkPen(0, 60, 160, 200),
                    }
                )
            self.points.setData(key_spots)
            self.points_x.setData([])  # Vector2用は非表示
            self.points_y.setData([])

        if getattr(self._track, "interp", None) == InterpMode.BEZIER:
            handle_spots = []
            line_x: list[float] = []
            line_y: list[float] = []
            for k in keys:
                key_id = id(k)
                for component, handle in (
                    ("handle_in", getattr(k, "handle_in", None)),
                    ("handle_out", getattr(k, "handle_out", None)),
                ):
                    if handle is None:
                        continue
                    handle_id = id(handle)
                    is_handle_sel = handle_id in selected_handle_ids
                    # Vector2Trackの場合、ハンドルをX/Yそれぞれのカーブ上に表示（時間軸方向にオフセット）
                    if is_vector2:
                        # 表示時間範囲の0.5%をオフセットとして使用
                        x_range = self.viewbox.viewRange()[0]
                        time_span = x_range[1] - x_range[0]
                        display_offset = max(0.005, time_span * 0.005)  # 最小0.005秒
                        
                        # Xカーブ上のハンドル（左にオフセット）
                        vx = k.vx if k.vx is not None else 0.0
                        handle_vx = handle.vx if handle.vx is not None else handle.v
                        handle_spots.append(
                            {
                                "pos": (handle.t - display_offset, handle_vx),
                                "data": (component + "_x", key_id, handle_id),
                                "brush": pg.mkBrush(255, 200, 80, 220)
                                if is_handle_sel
                                else pg.mkBrush(255, 100, 100, 200),
                                "size": 11 if is_handle_sel else 8,
                                "pen": pg.mkPen(200, 140, 40, 220)
                                if is_handle_sel
                                else pg.mkPen(200, 50, 50, 200),
                            }
                        )
                        line_x.extend([k.t, handle.t, float("nan")])
                        line_y.extend([vx, handle_vx, float("nan")])
                        
                        # Yカーブ上のハンドル（右にオフセット）
                        vy = k.vy if k.vy is not None else 0.0
                        handle_vy = handle.vy if handle.vy is not None else handle.v
                        handle_spots.append(
                            {
                                "pos": (handle.t + display_offset, handle_vy),
                                "data": (component + "_y", key_id, handle_id),
                                "brush": pg.mkBrush(255, 200, 80, 220)
                                if is_handle_sel
                                else pg.mkBrush(100, 100, 255, 200),
                                "size": 11 if is_handle_sel else 8,
                                "pen": pg.mkPen(200, 140, 40, 220)
                                if is_handle_sel
                                else pg.mkPen(50, 50, 200, 200),
                            }
                        )
                        line_x.extend([k.t, handle.t, float("nan")])
                        line_y.extend([vy, handle_vy, float("nan")])
                    else:
                        handle_pos = (handle.t, handle.v)
                        key_pos_v = k.v
                        handle_spots.append(
                            {
                                "pos": handle_pos,
                                "data": (component, key_id, handle_id),
                                "brush": pg.mkBrush(255, 200, 80, 220)
                                if is_handle_sel
                                else pg.mkBrush(90, 90, 90, 200),
                                "size": 11 if is_handle_sel else 8,
                                "pen": pg.mkPen(200, 140, 40, 220)
                                if is_handle_sel
                                else pg.mkPen(70, 70, 70, 200),
                            }
                        )
                        line_x.extend([k.t, handle.t, float("nan")])
                        line_y.extend([key_pos_v, handle_pos[1], float("nan")])
            self.handle_points.setData(handle_spots)
            if line_x and line_y:
                self.handle_lines.setData(line_x, line_y)
            else:
                self.handle_lines.setData([], [])
        else:
            self.handle_points.setData([])
            self.handle_lines.setData([], [])

    # ---- マウス位置取得 ----
    def get_mouse_time(self) -> Optional[float]:
        """マウスカーソル位置の時間（t）を取得。カーソルがプロット外の場合はNoneを返す。"""
        if self.plot is None:
            return None
        mouse_pos = self.plot.mapFromGlobal(QtGui.QCursor().pos())
        if not self.plot.rect().contains(mouse_pos):
            return None
        scene_pos = self.plot.mapToScene(mouse_pos)
        view_pos = self.viewbox.mapSceneToView(scene_pos)
        return float(max(0.0, view_pos.x()))

    # ---- レンジ制御 ----
    def fit_x(self, padding: float = 0.02) -> None:
        """Xレンジを[0, max(1.0, tmax)]に設定。"""
        if self._track is None:
            self.viewbox.setXRange(0.0, 1.0, padding=padding)
            return
        ks = self._track.sorted()
        tmax = max(self._duration_s, max((k.t for k in ks), default=0.0))
        self.viewbox.setXRange(0.0, max(1.0, tmax), padding=padding)

    def fit_y(self, padding: float = 0.05) -> None:
        """キー点に基づいてYレンジを設定（ゼロ幅/非有限は安全側に調整）。"""
        if self._track is None:
            self.viewbox.setYRange(-1.0, 1.0, padding=0)
            return

        ks = self._track.sorted()
        is_vector2 = getattr(self._track, "track_type", TrackType.SCALAR) == TrackType.VECTOR2
        
        if ks:
            if is_vector2:
                # Vector2Track: XとYの範囲を考慮
                vx_values = [k.vx if k.vx is not None else 0.0 for k in ks]
                vy_values = [k.vy if k.vy is not None else 0.0 for k in ks]
                all_values = vx_values + vy_values
                vmin = min(all_values)
                vmax = max(all_values)
            else:
                vmin = min(k.v for k in ks)
                vmax = max(k.v for k in ks)
        else:
            vmin, vmax = -1.0, 1.0

        # 非有限/極小レンジの保護
        if not np.isfinite(vmin) or not np.isfinite(vmax) or abs(vmax - vmin) < 1e-6:
            c = 0.5 * (vmin + vmax)
            vmin, vmax = c - 1.0, c + 1.0

        pad = padding * (vmax - vmin)
        self.viewbox.setYRange(vmin - pad, vmax + pad, padding=0)

    # ---- 参照ヘルパ ----
    @property
    def viewbox(self) -> pg.ViewBox:
        return self.plot.plotItem.vb

    # ---- 内部コールバック ----
    def _on_playback_playhead(self, playhead_s: float, _playing: bool) -> None:
        self.set_playhead(playhead_s)
