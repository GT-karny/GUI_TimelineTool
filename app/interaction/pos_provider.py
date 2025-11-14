# interaction/pos_provider.py
from __future__ import annotations
from PySide6.QtCore import QPointF
import pyqtgraph as pg

from .selection import KeyPoint

class SingleTrackPosProvider:
    """単一トラック用の KeyPosProvider 実装。track_id は Track.track_id を利用。"""

    def __init__(self, plot_widget: pg.PlotWidget, track, track_id: str | None = None):
        self.vb = plot_widget.plotItem.vb
        self.track = track
        self.track_id = track_id or getattr(track, "track_id", "0")

    def iter_all_keypoints(self):
        for k in self.track.sorted():
            yield KeyPoint(str(self.track_id), id(k), k.t, k.v)

    def scene_pos_of(self, kp: KeyPoint):
        return self.vb.mapViewToScene(QPointF(kp.t, kp.v))
