# interaction/pos_provider.py
from __future__ import annotations
from PySide6.QtCore import QPointF
import pyqtgraph as pg

from ..core.timeline import InterpMode
from .selection import KeyPoint

class SingleTrackPosProvider:
    """単一トラック用の KeyPosProvider 実装。track_id は Track.track_id を利用。"""

    def __init__(self, plot_widget: pg.PlotWidget, track, track_id: str | None = None):
        self.vb = plot_widget.plotItem.vb
        self.track = track
        self.track_id = track_id or getattr(track, "track_id", "0")

    def iter_all_keypoints(self):
        include_handles = getattr(self.track, "interp", None) == InterpMode.BEZIER
        for k in self.track.sorted():
            track_id = str(self.track_id)
            yield KeyPoint(track_id, id(k), k.t, k.v)
            if not include_handles:
                continue
            for component, handle in (
                ("handle_in", getattr(k, "handle_in", None)),
                ("handle_out", getattr(k, "handle_out", None)),
            ):
                if handle is None:
                    continue
                yield KeyPoint(
                    track_id,
                    id(k),
                    handle.t,
                    handle.v,
                    component=component,
                    item_id=id(handle),
                )

    def scene_pos_of(self, kp: KeyPoint):
        return self.vb.mapViewToScene(QPointF(kp.t, kp.v))

    def set_binding(self, plot_widget: pg.PlotWidget, track, track_id: str | None = None) -> None:
        self.vb = plot_widget.plotItem.vb
        self.track = track
        if track_id is not None:
            self.track_id = str(track_id)
        else:
            self.track_id = getattr(track, "track_id", self.track_id)
