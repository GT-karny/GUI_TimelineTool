"""Test-time stubs for optional Qt dependencies.

This project relies on PySide6 and pyqtgraph for the GUI runtime. In the
execution environment used for automated checks the native Qt libraries (most
notably ``libGL``) are unavailable which makes importing those modules fail at
import time.  To keep the application code importable for unit tests we install
very small stub modules that mimic the tiny subset of the APIs used in tests.

When the real libraries are available this module keeps out of the way because
``PySide6`` can be imported successfully and the stubs are never created. To
avoid masking configuration errors in production the stubs are only activated
when the ``TIMELINE_TOOL_USE_QT_STUBS`` environment variable is set to a truthy
value (``1``, ``true``, ``yes``).
"""

from __future__ import annotations

import os
import sys
import types


def _is_truthy(value: str) -> bool:
    return value.lower() in {"1", "true", "yes"}
_USE_QT_STUBS = _is_truthy(os.environ.get("TIMELINE_TOOL_USE_QT_STUBS", ""))


def _install_pyside6_stub() -> None:
    if "PySide6" in sys.modules:
        return

    pyside6 = types.ModuleType("PySide6")
    pyside6.__path__ = []  # type: ignore[attr-defined]
    qtcore = types.ModuleType("PySide6.QtCore")
    qtwidgets = types.ModuleType("PySide6.QtWidgets")
    qtgui = types.ModuleType("PySide6.QtGui")

    class QObject:  # pragma: no cover - trivial stub
        def __init__(self, *_args, **_kwargs):
            pass

    class QEvent:  # pragma: no cover - trivial stub
        GraphicsSceneMousePress = 1
        GraphicsSceneMouseMove = 2
        GraphicsSceneMouseRelease = 3
        GraphicsSceneMouseDoubleClick = 4
        GraphicsSceneWheel = 5

    class Qt:  # pragma: no cover - trivial stub
        LeftButton = 1
        MiddleButton = 2
        RightButton = 4
        ShiftModifier = 0x02000000

    class Signal:  # pragma: no cover - trivial stub
        def __init__(self, *_args, **_kwargs):
            self._slots: list = []

        def connect(self, slot) -> None:
            self._slots.append(slot)

        def emit(self, *args, **kwargs) -> None:
            for slot in list(self._slots):
                try:
                    slot(*args, **kwargs)
                except TypeError:
                    slot()

    class QPointF:  # pragma: no cover - trivial stub
        def __init__(self, x: float = 0.0, y: float = 0.0):
            self._x = float(x)
            self._y = float(y)

        def x(self) -> float:
            return self._x

        def y(self) -> float:
            return self._y

    class QRectF:  # pragma: no cover - trivial stub
        def __init__(self, p1: QPointF, p2: QPointF):
            self._left = min(p1.x(), p2.x())
            self._right = max(p1.x(), p2.x())
            self._top = min(p1.y(), p2.y())
            self._bottom = max(p1.y(), p2.y())

        def normalized(self) -> "QRectF":
            return self

        def setRect(self, left: float, top: float, width: float, height: float) -> None:
            self._left = left
            self._top = top
            self._right = left + width
            self._bottom = top + height

        def contains(self, point: QPointF) -> bool:
            return (
                self._left <= point.x() <= self._right
                and self._top <= point.y() <= self._bottom
            )

        def rect(self) -> "QRectF":
            return self

    class QSettings:  # pragma: no cover - trivial stub
        def __init__(self, *_args, **_kwargs):
            self._values: dict[str, object] = {}

        def value(self, key: str, default=None):
            return self._values.get(key, default)

        def setValue(self, key: str, value) -> None:
            self._values[key] = value

        def sync(self) -> None:
            pass

        def remove(self, key: str) -> None:
            self._values.pop(key, None)

    qtcore.QObject = QObject
    qtcore.QEvent = QEvent
    qtcore.Qt = Qt
    qtcore.Signal = Signal
    qtcore.QPointF = QPointF
    qtcore.QRectF = QRectF
    qtcore.QSettings = QSettings

    class QApplication:  # pragma: no cover - trivial stub
        _instance = None
        _buttons = 0

        def __init__(self, _args=None):
            QApplication._instance = self

        @staticmethod
        def instance() -> "QApplication | None":
            return QApplication._instance

        @staticmethod
        def mouseButtons() -> int:
            return QApplication._buttons

    class QAction:  # pragma: no cover - trivial stub
        def __init__(self, text: str):
            self.text = text

    class QUndoCommand:  # pragma: no cover - trivial stub
        def __init__(self, text: str = "", parent: "QUndoCommand | None" = None):
            self._text = text
            self._children: list[QUndoCommand] = []
            if parent is not None:
                parent._children.append(self)

        def redo(self) -> None:
            pass

        def undo(self) -> None:
            pass

        def childCount(self) -> int:
            return len(self._children)

    class QWidget(QObject):  # pragma: no cover - trivial stub
        def __init__(self, parent=None):
            super().__init__()
            self._parent = parent
            self._visible = False

        def show(self) -> None:
            self._visible = True

    class QMenu:  # pragma: no cover - trivial stub
        def __init__(self, _parent=None):
            self._actions: list[QAction] = []

        def addAction(self, text: str) -> QAction:
            action = QAction(text)
            self._actions.append(action)
            return action

        def exec(self, _pos):
            return None

    class QGraphicsRectItem:  # pragma: no cover - trivial stub
        def __init__(self):
            self._rect = None

        def setPen(self, _pen) -> None:
            pass

        def setBrush(self, _brush) -> None:
            pass

        def setRect(self, rect: QRectF) -> None:
            self._rect = rect

        def rect(self) -> QRectF | None:
            return self._rect

    class QGraphicsScene:  # pragma: no cover - trivial stub
        def __init__(self):
            self._items: list[QGraphicsRectItem] = []

        def addItem(self, item) -> None:
            self._items.append(item)

        def removeItem(self, item) -> None:
            if item in self._items:
                self._items.remove(item)

        def installEventFilter(self, _filter) -> None:
            pass

    class QGroupBox(QWidget):  # pragma: no cover - trivial stub
        def __init__(self, title: str = "", parent=None):
            super().__init__(parent)
            self._title = title

    class QFormLayout:  # pragma: no cover - trivial stub
        class FieldGrowthPolicy:  # pragma: no cover - trivial stub
            ExpandingFieldsGrow = 0

        def __init__(self, _parent=None):
            self._rows: list[tuple[str | None, QWidget]] = []

        def setFieldGrowthPolicy(self, _policy) -> None:
            pass

        def addRow(self, label, widget: QWidget | None = None) -> None:
            if widget is None and isinstance(label, QWidget):
                widget = label
                label = None
            self._rows.append((label, widget))

    class QCheckBox(QWidget):  # pragma: no cover - trivial stub
        def __init__(self, text: str = "", parent=None):
            super().__init__(parent)
            self._text = text
            self._checked = False
            self.toggled = Signal(bool)

        def setChecked(self, value: bool) -> None:
            self._checked = bool(value)
            self.toggled.emit(self._checked)

        def isChecked(self) -> bool:
            return self._checked

    class QLineEdit(QWidget):  # pragma: no cover - trivial stub
        def __init__(self, parent=None):
            super().__init__(parent)
            self._text = ""
            self.editingFinished = Signal()

        def setPlaceholderText(self, _text: str) -> None:
            pass

        def setText(self, text: str) -> None:
            self._text = text

        def text(self) -> str:
            return self._text

        def clear(self) -> None:
            self._text = ""

    class QSpinBox(QWidget):  # pragma: no cover - trivial stub
        def __init__(self, parent=None):
            super().__init__(parent)
            self._value = 0
            self.valueChanged = Signal(int)

        def setRange(self, _min: int, _max: int) -> None:
            pass

        def setValue(self, value: int) -> None:
            self._value = int(value)
            self.valueChanged.emit(self._value)

        def value(self) -> int:
            return self._value

    qtgui.QUndoCommand = QUndoCommand

    qtwidgets.QWidget = QWidget

    qtwidgets.QApplication = QApplication
    qtwidgets.QMenu = QMenu
    qtwidgets.QGraphicsRectItem = QGraphicsRectItem
    qtwidgets.QGraphicsScene = QGraphicsScene
    qtwidgets.QGroupBox = QGroupBox
    qtwidgets.QFormLayout = QFormLayout
    qtwidgets.QCheckBox = QCheckBox
    qtwidgets.QLineEdit = QLineEdit
    qtwidgets.QSpinBox = QSpinBox

    sys.modules["PySide6"] = pyside6
    sys.modules["PySide6.QtCore"] = qtcore
    sys.modules["PySide6.QtWidgets"] = qtwidgets
    sys.modules["PySide6.QtGui"] = qtgui
    pyside6.QtCore = qtcore
    pyside6.QtWidgets = qtwidgets
    pyside6.QtGui = qtgui


def _install_pyqtgraph_stub() -> None:
    if "pyqtgraph" in sys.modules:
        return

    pg = types.ModuleType("pyqtgraph")

    class _DummyViewBox:  # pragma: no cover - trivial stub
        def translateBy(self, **_kwargs) -> None:
            pass

        def scaleBy(self, *_args, **_kwargs) -> None:
            pass

    class _DummyPlotItem:  # pragma: no cover - trivial stub
        def __init__(self):
            self.vb = _DummyViewBox()

    class PlotWidget:  # pragma: no cover - trivial stub
        def __init__(self):
            from PySide6.QtWidgets import QGraphicsScene  # type: ignore

            self._scene = QGraphicsScene()
            self.plotItem = _DummyPlotItem()

        def scene(self):
            return self._scene

        def deleteLater(self) -> None:
            pass

    def mkPen(*_args, **_kwargs):  # pragma: no cover - trivial stub
        return None

    def mkBrush(*_args, **_kwargs):  # pragma: no cover - trivial stub
        return None

    pg.PlotWidget = PlotWidget
    pg.mkPen = mkPen
    pg.mkBrush = mkBrush

    sys.modules["pyqtgraph"] = pg


if _USE_QT_STUBS:  # pragma: no branch - simple configuration gate
    try:  # pragma: no cover - executed during import
        import PySide6.QtGui  # type: ignore # noqa: F401
        import PySide6.QtWidgets  # type: ignore # noqa: F401
    except Exception:  # pragma: no cover - executed when Qt missing
        for name in list(sys.modules):
            if name.startswith("PySide6"):
                sys.modules.pop(name)
        _install_pyside6_stub()
        _install_pyqtgraph_stub()
