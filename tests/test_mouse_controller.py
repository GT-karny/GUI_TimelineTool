import importlib
import os
from typing import Dict, Iterable

os.environ.setdefault("TIMELINE_TOOL_USE_QT_STUBS", "1")

import sitecustomize  # noqa: F401  # ensure Qt stubs are installed before imports

importlib.reload(sitecustomize)

import pytest
from PySide6 import QtCore, QtWidgets
import pyqtgraph as pg

from app.core.timeline import Timeline, Keyframe
from app.interaction.mouse_controller import MouseController
from app.interaction.selection import SelectionManager, KeyPoint, KeyPosProvider


class DummyProvider(KeyPosProvider):
    """Minimal key position provider backed by a dictionary."""

    def __init__(self, mapping: Dict[KeyPoint, QtCore.QPointF]):
        self._mapping = mapping

    def iter_all_keypoints(self) -> Iterable[KeyPoint]:
        return self._mapping.keys()

    def scene_pos_of(self, kp: KeyPoint) -> QtCore.QPointF:
        return self._mapping[kp]


@pytest.fixture(scope="module")
def qapp() -> QtWidgets.QApplication:
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


def _build_controller(qapp: QtWidgets.QApplication) -> tuple[MouseController, Timeline, pg.PlotWidget]:
    timeline = Timeline()
    plot = pg.PlotWidget()
    key = timeline.track.keys[0]
    kp = KeyPoint(track_id=0, key_id=id(key), t=key.t, v=key.v)
    provider = DummyProvider({kp: QtCore.QPointF(key.t, key.v)})
    selection = SelectionManager(plot.scene(), provider)
    controller = MouseController(
        plot_widget=plot,
        timeline=timeline,
        selection=selection,
        pos_provider=provider,
        on_changed=lambda: None,
        set_playhead=lambda _: None,
        commit_drag=None,
    )
    return controller, timeline, plot


def test_key_drag_lifecycle(qapp) -> None:
    controller, timeline, plot = _build_controller(qapp)
    key = timeline.track.keys[0]
    hit = KeyPoint(track_id=0, key_id=id(key), t=key.t, v=key.v)
    commits: list[tuple[Keyframe, tuple[float, float], tuple[float, float]]] = []
    controller.commit_drag = lambda k, start, end: commits.append((k, start, end))

    controller._begin_key_drag(hit)
    controller._scene_to_view = lambda _pos: QtCore.QPointF(2.0, 3.0)
    controller._update_key_drag(QtCore.QPointF(0.0, 0.0))
    controller._end_key_drag()

    assert pytest.approx(key.t) == 2.0
    assert pytest.approx(key.v) == 3.0
    assert commits == [(key, (0.0, 0.0), (2.0, 3.0))]
    assert not controller._key_drag.active
    plot.deleteLater()


def test_create_keyframe_fallback(qapp) -> None:
    controller, timeline, plot = _build_controller(qapp)
    existing_len = len(timeline.track.keys)
    created = controller._create_keyframe(10.0, 5.0)

    assert isinstance(created, Keyframe)
    assert len(timeline.track.keys) == existing_len + 1
    assert created.t == pytest.approx(10.0)
    assert created.v == pytest.approx(5.0)
    plot.deleteLater()
