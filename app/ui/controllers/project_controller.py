from __future__ import annotations

from pathlib import Path
from typing import Optional, TYPE_CHECKING

from PySide6 import QtWidgets

from ...core.timeline import Timeline
from ...io.project_io import load_project, save_project

if TYPE_CHECKING:  # pragma: no cover - imported for type checking only
    from ..main_window import MainWindow


class ProjectController:
    """Encapsulates project lifecycle operations for the main window."""

    def __init__(self, window: "MainWindow") -> None:
        self._window = window
        self._current_project_path: Optional[Path] = None

    # -------------------- Properties --------------------
    @property
    def current_project_path(self) -> Optional[Path]:
        return self._current_project_path

    # -------------------- Project lifecycle --------------------
    def apply_project(
        self,
        timeline: Timeline,
        *,
        sample_rate: Optional[float] = None,
        path: Optional[Path] = None,
    ) -> None:
        self._window.apply_project_state(timeline, sample_rate=sample_rate)

        self._current_project_path = path
        self._update_window_title()

    def on_new_file(self) -> None:
        self.apply_project(Timeline(), sample_rate=90.0, path=None)
        self._window.statusBar().showMessage("Started new project", 3000)

    def on_load_file(self) -> None:
        start_dir = str(self._current_project_path or "")
        path_str, _ = QtWidgets.QFileDialog.getOpenFileName(
            self._window,
            "Load Timeline Project",
            start_dir,
            "Timeline Project (*.json);;All Files (*)",
        )
        if not path_str:
            return

        path = Path(path_str)
        try:
            timeline, sample_rate = load_project(path)
        except Exception as exc:  # pragma: no cover - Qt dialog side effect
            QtWidgets.QMessageBox.critical(self._window, "Load Failed", f"{exc}")
            return

        self.apply_project(timeline, sample_rate=sample_rate, path=path)
        self._window.statusBar().showMessage(f"Loaded project: {path}", 3000)

    def on_save_file(self) -> None:
        if self._current_project_path is None:
            self.on_save_file_as()
            return
        self._save_to_path(self._current_project_path)

    def on_save_file_as(self) -> None:
        if self._current_project_path is None:
            start_dir = Path.cwd()
            default_name = "timeline.json"
        else:
            start_dir = self._current_project_path.parent
            default_name = self._current_project_path.name

        path_str, _ = QtWidgets.QFileDialog.getSaveFileName(
            self._window,
            "Save Timeline Project",
            str(start_dir / default_name),
            "Timeline Project (*.json);;All Files (*)",
        )
        if not path_str:
            return

        self._save_to_path(Path(path_str))

    # -------------------- Helpers --------------------
    def _update_window_title(self) -> None:
        if self._current_project_path is None:
            suffix = "Untitled"
        else:
            suffix = self._current_project_path.name
        self._window.setWindowTitle(f"{self._window._base_title} - {suffix}")

    def _save_to_path(self, path: Path) -> bool:
        try:
            save_project(path, self._window.timeline, self._window.sample_rate_hz)
        except Exception as exc:  # pragma: no cover - Qt dialog side effect
            QtWidgets.QMessageBox.critical(self._window, "Save Failed", f"{exc}")
            return False

        self._current_project_path = path
        self._window.undo.setClean()
        self._update_window_title()
        self._window.statusBar().showMessage(f"Saved project: {path}", 3000)
        return True

    def update_window_title(self) -> None:
        """Public wrapper to refresh the window title."""
        self._update_window_title()
