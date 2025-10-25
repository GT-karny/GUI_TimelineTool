from PySide6 import QtWidgets
from .ui.main_window import MainWindow
import sys

def main():
    app = QtWidgets.QApplication(sys.argv)
    win = MainWindow(); win.show()
    sys.exit(app.exec())

if __name__ == "__main__": main()
