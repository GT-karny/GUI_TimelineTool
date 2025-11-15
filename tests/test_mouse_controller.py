from __future__ import annotations

import importlib
import os
import sys
from types import SimpleNamespace
from typing import Callable, Dict, Iterable, List, Optional, Tuple

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

from app.core.timeline import Timeline
from app.interaction.mouse_controller import MouseController
from app.interaction.selection import KeyPoint, KeyPosProvider, SelectionManager
from app.interaction.key_edit_service import KeyEditService


class PlotWidgetStub(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self._scene = QtWidgets.QGraphicsScene()
        self.plotItem = SimpleNamespace(
            vb=SimpleNamespace(
                mapSceneToView=lambda p: p,
                translateBy=lambda **_kwargs: None,
                scaleBy=lambda *_args, **_kwargs: None,
            )
        )

    def scene(self):
        return self._scene

    def deleteLater(self) -> None:
        pass


class DummyProvider(KeyPosProvider):
    """Minimal key position provider backed by a dictionary."""

    def __init__(self, mapping: Dict[KeyPoint, QtCore.QPointF], track_id: str):
        self._mapping = mapping
        self.track_id = track_id

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


def _build_controller(
    qapp: QtWidgets.QApplication,
    *,
    key_edit: Optional[object] = None,
    on_changed: Optional[Callable[[], None]] = None,
) -> Tuple[MouseController, Timeline, PlotWidgetStub, SelectionManager]:
    timeline = Timeline()
    plot = PlotWidgetStub()
    key = timeline.track.keys[0]
    track_id = timeline.track.track_id
    kp = KeyPoint(track_id=track_id, key_id=id(key), t=key.t, v=key.v)
    provider = DummyProvider({kp: QtCore.QPointF(key.t, key.v)}, track_id=track_id)
    selection = SelectionManager(plot.scene(), provider)
    if key_edit is None:
        key_edit = KeyEditService(timeline, selection, provider)
    if on_changed is None:
        on_changed = lambda: None
    controller = MouseController(
        plot_widget=plot,
        timeline=timeline,
        selection=selection,
        pos_provider=provider,
        on_changed=on_changed,
        set_playhead=lambda _: None,
        key_edit=key_edit,
    )
    return controller, timeline, plot, selection


class RecordingKeyEdit:
    def __init__(self) -> None:
        self.calls: List[Tuple[str, object]] = []
        self.update_result = False
        self.add_result: Optional[object] = object()
        self.delete_result = False

    def begin_drag(self, hit: KeyPoint) -> None:
        self.calls.append(("begin", hit))

    def update_drag(self, scene_pos: QtCore.QPointF, scene_to_view: Callable[[QtCore.QPointF], QtCore.QPointF]) -> bool:
        self.calls.append(("update", scene_pos))
        return self.update_result

    def commit_drag(self) -> bool:
        self.calls.append(("commit", None))
        return True

    def add_at(self, time: float, value: float):
        self.calls.append(("add", time, value))
        return self.add_result

    def delete_at(self, scene_pos: QtCore.QPointF, *, px_thresh: int = 10) -> bool:
        self.calls.append(("delete", scene_pos, px_thresh))
        return self.delete_result


class FakeMouseEvent:
    def __init__(self, scene_pos: QtCore.QPointF, button, modifiers: int = 0):
        self._scene_pos = scene_pos
        self._button = button
        self._modifiers = modifiers

    def scenePos(self) -> QtCore.QPointF:
        return self._scene_pos

    def button(self):
        return self._button

    def modifiers(self) -> int:
        return self._modifiers


class FakeContextEvent:
    def __init__(self, scene_pos: QtCore.QPointF):
        self._scene_pos = scene_pos

    def scenePos(self) -> QtCore.QPointF:
        return self._scene_pos

    def screenPos(self) -> QtCore.QPointF:
        return self._scene_pos


def test_drag_flow_uses_service(qapp) -> None:
    service = RecordingKeyEdit()
    service.update_result = True
    changes: List[str] = []
    controller, timeline, plot, selection = _build_controller(
        qapp, key_edit=service, on_changed=lambda: changes.append("changed")
    )
    key = timeline.track.keys[0]
    hit = KeyPoint(track_id=timeline.track.track_id, key_id=id(key), t=key.t, v=key.v)
    controller.sel.hit_test_nearest = lambda *_args, **_kwargs: hit  # type: ignore
    controller._scene_to_view = lambda p: p

    press_ev = FakeMouseEvent(QtCore.QPointF(0.0, 0.0), QtCore.Qt.LeftButton)
    move_ev = FakeMouseEvent(QtCore.QPointF(1.0, 2.0), QtCore.Qt.LeftButton)
    release_ev = FakeMouseEvent(QtCore.QPointF(1.0, 2.0), QtCore.Qt.LeftButton)

    controller._handle_left_button_press(press_ev)
    controller._handle_left_button_move(move_ev)
    controller._handle_left_button_release(release_ev)

    assert ("begin", hit) in service.calls
    assert ("commit", None) in service.calls
    assert any(call[0] == "update" for call in service.calls)
    assert changes  # on_changed invoked
    plot.deleteLater()


def test_double_click_adds_via_service(qapp) -> None:
    service = RecordingKeyEdit()
    service.add_result = object()
    changes: List[str] = []
    controller, _, plot, _ = _build_controller(
        qapp, key_edit=service, on_changed=lambda: changes.append("changed")
    )
    controller._scene_to_view = lambda p: p

    dbl_event = FakeMouseEvent(QtCore.QPointF(3.0, 4.0), QtCore.Qt.LeftButton)
    controller._handle_left_button_double_click(dbl_event)

    assert ("add", 3.0, 4.0) in service.calls
    assert changes  # refresh triggered
    plot.deleteLater()


def test_context_menu_add_and_delete(monkeypatch, qapp) -> None:
    service = RecordingKeyEdit()
    service.add_result = object()
    service.delete_result = True
    changes: List[str] = []
    controller, _, plot, _ = _build_controller(
        qapp, key_edit=service, on_changed=lambda: changes.append("changed")
    )
    controller._scene_to_view = lambda p: p

    class FakeMenu:
        result_choice = ""

        def __init__(self, *_args, **_kwargs):
            self.actions: Dict[str, object] = {}

        def addAction(self, text: str):
            action = object()
            self.actions[text] = action
            return action

        def exec(self, _pos):
            return self.actions.get(self.result_choice)

    monkeypatch.setattr(QtWidgets, "QMenu", FakeMenu)

    FakeMenu.result_choice = "Add Key Here"
    controller._show_context_menu(FakeContextEvent(QtCore.QPointF(1.0, 2.0)))
    assert any(call[0] == "add" for call in service.calls)

    FakeMenu.result_choice = "Delete Nearest"
    controller._show_context_menu(FakeContextEvent(QtCore.QPointF(1.0, 2.0)))
    assert any(call[0] == "delete" for call in service.calls)

    assert changes  # refresh triggered at least once
    plot.deleteLater()
