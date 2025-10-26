"""Playback controller managing playhead progression and looping."""
from __future__ import annotations

import time
from typing import Optional

from PySide6 import QtCore

from ..core.timeline import Timeline


def _parse_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, str):
        return value.lower() in {"1", "true", "yes", "on"}
    return bool(value)


class PlaybackController(QtCore.QObject):
    """Controls playback state, loop mode, and playhead updates."""

    playhead_changed = QtCore.Signal(float, bool)
    playing_changed = QtCore.Signal(bool)
    loop_enabled_changed = QtCore.Signal(bool)

    def __init__(
        self,
        timeline: Timeline,
        qsettings: QtCore.QSettings,
        fps: int = 60,
        parent: Optional[QtCore.QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._timeline = timeline
        self._qsettings = qsettings
        self._fps = max(1, int(fps))

        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(int(1000 / self._fps))
        self._timer.timeout.connect(self._on_tick)

        self._playing = False
        self._playhead_s = 0.0
        self._start_playhead_s = 0.0
        self._start_perf_ns: Optional[int] = None

        raw_loop = self._qsettings.value("playback/loop_enabled", False)
        self._loop_enabled = _parse_bool(raw_loop)

    # ------------------------------------------------------------------
    # Properties
    @property
    def playhead(self) -> float:
        return self._playhead_s

    @property
    def is_playing(self) -> bool:
        return self._playing

    @property
    def loop_enabled(self) -> bool:
        return self._loop_enabled

    @loop_enabled.setter
    def loop_enabled(self, value: bool) -> None:
        enabled = bool(value)
        if self._loop_enabled == enabled:
            return
        self._loop_enabled = enabled
        self._qsettings.setValue("playback/loop_enabled", enabled)
        self.loop_enabled_changed.emit(enabled)

    # ------------------------------------------------------------------
    # Public control methods
    def set_timeline(self, timeline: Timeline) -> None:
        if timeline is self._timeline:
            return
        self.stop()
        self._timeline = timeline
        self.set_playhead(min(self._playhead_s, float(self._timeline.duration_s)))

    def set_playhead(self, value: float) -> None:
        duration = max(0.0, float(self._timeline.duration_s))
        clamped = max(0.0, min(float(value), duration))
        self._playhead_s = clamped
        self._start_playhead_s = clamped
        if self._playing:
            self._start_perf_ns = time.perf_counter_ns()
        else:
            self._start_perf_ns = None
        self._emit_playhead()

    def clamp_to_duration(self) -> None:
        self.set_playhead(self._playhead_s)

    def play(self) -> None:
        if self._playing:
            return
        self._start_playhead_s = self._playhead_s
        self._start_perf_ns = time.perf_counter_ns()
        self._timer.start()
        self._set_playing(True)

    def pause(self) -> None:
        if not self._playing:
            return
        self._timer.stop()
        self._start_perf_ns = None
        self._set_playing(False)

    def stop(self) -> None:
        self._timer.stop()
        self._start_perf_ns = None
        self._set_playing(False)

    def toggle(self) -> None:
        if self._playing:
            self.pause()
        else:
            self.play()

    # ------------------------------------------------------------------
    # Internal helpers
    def _set_playing(self, value: bool) -> None:
        if self._playing == value:
            return
        self._playing = value
        self.playing_changed.emit(value)
        self._emit_playhead()

    def _emit_playhead(self) -> None:
        self.playhead_changed.emit(self._playhead_s, self._playing)

    def _on_tick(self) -> None:
        if not self._playing or self._start_perf_ns is None:
            return

        now_ns = time.perf_counter_ns()
        elapsed_s = (now_ns - self._start_perf_ns) / 1e9
        candidate = self._start_playhead_s + elapsed_s
        duration = max(0.0, float(self._timeline.duration_s))

        if duration <= 0.0:
            self._playhead_s = 0.0
            self._timer.stop()
            self._start_perf_ns = None
            self._set_playing(False)
            return

        if candidate >= duration:
            if self._loop_enabled:
                cycles = int(candidate // duration)
                candidate -= cycles * duration
                if candidate >= duration:
                    candidate = 0.0
                self._playhead_s = candidate
                self._start_playhead_s = candidate
                self._start_perf_ns = now_ns
                self._emit_playhead()
                return

            self._playhead_s = duration
            self._timer.stop()
            self._start_perf_ns = None
            self._set_playing(False)
            return

        if candidate < 0.0:
            # 逆再生などは未サポートのため clamp
            candidate = 0.0

        self._playhead_s = candidate
        self._emit_playhead()
