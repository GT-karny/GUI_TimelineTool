# playback/player.py
from __future__ import annotations
from typing import Callable, Optional, Tuple
from PySide6 import QtCore

from ..core.timeline import Timeline


class Player(QtCore.QObject):
    """
    再生ロジックのみ担当：
      - fps ベースの QTimer 駆動
      - 再生速度（speed）
      - 区間ループ（loop_range）
      - 外部 UI には set_playhead(t) コールバックで通知
    """

    def __init__(self, timeline: Timeline, set_playhead: Callable[[float], None], fps: int = 60):
        super().__init__()
        self.timeline = timeline
        self._set_playhead = set_playhead

        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._on_tick)
        self._fps = fps
        self._timer.setInterval(int(1000 / max(1, self._fps)))

        self._speed: float = 1.0               # 1.0 = 等速
        self._loop: Optional[Tuple[float, float]] = None  # (start, end) in seconds
        self._t0: Optional[QtCore.QTime] = None  # 再生開始の実時間
        self._offset_s: float = 0.0             # 再生開始時のタイムライン時刻

    # ---- Public API ----
    def play(self) -> None:
        if self._t0 is None:
            self._t0 = QtCore.QTime.currentTime()
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()
        self._t0 = None  # 完全停止（次回 play で原点から）

    def pause(self) -> None:
        self._timer.stop()  # ポーズ（_t0 は残す）

    def toggle(self) -> None:
        if self._timer.isActive():
            self.pause()
        else:
            self.play()

    def is_playing(self) -> bool:
        return self._timer.isActive()

    def set_fps(self, fps: int) -> None:
        self._fps = int(max(1, fps))
        self._timer.setInterval(int(1000 / self._fps))

    def set_speed(self, speed: float) -> None:
        """負値で逆再生も可（必要なら clamp しても良い）"""
        self._speed = float(speed)

    def set_loop(self, start_s: Optional[float], end_s: Optional[float]) -> None:
        """None, None でループ解除。start<end のときのみ有効。"""
        if start_s is None or end_s is None or end_s <= start_s:
            self._loop = None
        else:
            self._loop = (max(0.0, float(start_s)), float(end_s))

    def seek(self, t_s: float) -> None:
        """任意位置へジャンプ（再生中も可）。"""
        self._offset_s = float(max(0.0, t_s))
        self._t0 = QtCore.QTime.currentTime()  # 直近時刻を原点に
        self._emit(self._offset_s)

    # ---- Tick ----
    def _on_tick(self) -> None:
        if self._t0 is None:
            return
        wall = self._t0.msecsTo(QtCore.QTime.currentTime()) / 1000.0
        t = self._offset_s + wall * self._speed

        start, end = 0.0, self.timeline.duration_s
        if self._loop is not None:
            start, end = self._loop

        length = max(1e-6, end - start)

        # 速度に応じたループ計算（負速度もOK）
        rel = (t - start) % length
        t_play = start + rel

        self._emit(t_play)

    # ---- Notify ----
    def _emit(self, t: float) -> None:
        self._set_playhead(float(t))
