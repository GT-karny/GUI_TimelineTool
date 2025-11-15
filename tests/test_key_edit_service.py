from __future__ import annotations

import importlib
import os
import sys
from typing import Dict, Iterable, List, Tuple

import pytest

_existing_modules = set(sys.modules)
_previous_env = os.environ.get("TIMELINE_TOOL_USE_QT_STUBS")
_using_stubs = False

try:
    QtCore = importlib.import_module("PySide6.QtCore")
    QtWidgets = importlib.import_module("PySide6.QtWidgets")
except Exception:  # pragma: no cover - executed when Qt missing
    _using_stubs = True
    os.environ["TIMELINE_TOOL_USE_QT_STUBS"] = "1"
    sitecustomize = importlib.import_module("sitecustomize")
    importlib.reload(sitecustomize)
    QtCore = importlib.import_module("PySide6.QtCore")
    QtWidgets = importlib.import_module("PySide6.QtWidgets")
finally:
    if _previous_env is None:
        os.environ.pop("TIMELINE_TOOL_USE_QT_STUBS", None)
    else:
        os.environ["TIMELINE_TOOL_USE_QT_STUBS"] = _previous_env

_stub_modules = (
    {name for name in sys.modules if name not in _existing_modules and name.startswith("PySide6")}
    if _using_stubs
    else set()
)


@pytest.fixture(scope="module", autouse=True)
def _cleanup_qt_stubs():
    try:
        yield
    finally:
        for name in _stub_modules:
            sys.modules.pop(name, None)


from PySide6.QtGui import QUndoCommand

from app.actions.undo_commands import AddKeyCommand, DeleteKeysCommand, MoveKeyCommand
from app.core.timeline import Keyframe, Timeline
from app.interaction.key_edit_service import KeyEditService
from app.interaction.selection import KeyPoint, KeyPosProvider, SelectionManager


class DummyProvider(KeyPosProvider):
    def __init__(self, mapping: Dict[KeyPoint, QtCore.QPointF], track_id: str):
        self._mapping = mapping
        self.track_id = track_id

    def iter_all_keypoints(self) -> Iterable[KeyPoint]:
        return self._mapping.keys()

    def scene_pos_of(self, kp: KeyPoint) -> QtCore.QPointF:
        return self._mapping[kp]


class RecordingUndo:
    def __init__(self) -> None:
        self.commands: List[QUndoCommand] = []

    def push(self, cmd: QUndoCommand) -> None:
        cmd.redo()
        self.commands.append(cmd)


@pytest.fixture
def qapp():
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


class PlotStub:
    def __init__(self) -> None:
        self._scene = QtWidgets.QGraphicsScene()

    def scene(self):
        return self._scene

    def deleteLater(self) -> None:
        pass


def _make_service() -> Tuple[KeyEditService, Timeline, SelectionManager, DummyProvider, RecordingUndo, PlotStub]:
    timeline = Timeline()
    plot = PlotStub()
    track = timeline.track
    key = track.keys[0]
    track_id = track.track_id
    kp = KeyPoint(track_id=track_id, key_id=id(key), t=key.t, v=key.v)
    provider = DummyProvider({kp: QtCore.QPointF(key.t, key.v)}, track_id)
    selection = SelectionManager(plot.scene(), provider)
    undo = RecordingUndo()
    service = KeyEditService(timeline, selection, provider, push_undo=undo.push)
    return service, timeline, selection, provider, undo, plot


def test_drag_commit_pushes_move_command(qapp) -> None:
    service, timeline, selection, provider, undo, plot = _make_service()
    key = timeline.track.keys[0]
    hit = KeyPoint(track_id=timeline.track.track_id, key_id=id(key), t=key.t, v=key.v)
    scene_to_view = lambda _pos: QtCore.QPointF(2.0, 3.0)

    service.begin_drag(hit)
    assert service.update_drag(QtCore.QPointF(0.0, 0.0), scene_to_view)
    service.commit_drag()

    assert pytest.approx(key.t) == 2.0
    assert pytest.approx(key.v) == 3.0
    assert any(isinstance(cmd, MoveKeyCommand) for cmd in undo.commands)
    plot.deleteLater()


def test_add_at_uses_undo_and_selects_key(qapp) -> None:
    service, timeline, selection, provider, undo, plot = _make_service()
    selection.clear()

    created = service.add_at(10.0, 5.0)

    assert isinstance(created, Keyframe)
    assert len(timeline.track.keys) >= 3
    assert any(isinstance(cmd, AddKeyCommand) for cmd in undo.commands)
    assert selection.selected
    sel = next(iter(selection.selected))
    assert sel.key_id == id(created)
    plot.deleteLater()


def test_delete_at_uses_undo_and_updates_selection(qapp) -> None:
    service, timeline, selection, provider, undo, plot = _make_service()
    key = timeline.track.keys[0]
    selection.set_single(timeline.track.track_id, id(key))
    scene_pos = QtCore.QPointF(key.t, key.v)

    deleted = service.delete_at(scene_pos, px_thresh=9999)

    assert deleted
    assert any(isinstance(cmd, DeleteKeysCommand) for cmd in undo.commands)
    assert all(sel.key_id != id(key) for sel in selection.selected)
    assert key not in timeline.track.keys
    plot.deleteLater()
