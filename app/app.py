import logging
import sys
from pathlib import Path

from PySide6 import QtWidgets

if __package__ is None or __package__ == "":
    # Ensure the project root is on sys.path so absolute imports succeed when
    # the script is executed as a top-level entry point (e.g., from PyInstaller).
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.ui.main_window import MainWindow

def main():
    logging.basicConfig(level=logging.INFO)
    app = QtWidgets.QApplication(sys.argv)
    win = MainWindow(); win.show()
    sys.exit(app.exec())

if __name__ == "__main__": main()
