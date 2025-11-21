from PySide6 import QtGui, QtWidgets
from PySide6.QtCore import Qt

def apply_dark_theme(app: QtWidgets.QApplication) -> None:
    """Apply a dark theme to the application using Fusion style and a custom palette."""
    app.setStyle("Fusion")

    palette = QtGui.QPalette()
    
    # Base colors
    dark_gray = QtGui.QColor(53, 53, 53)
    gray = QtGui.QColor(128, 128, 128)
    black = QtGui.QColor(25, 25, 25)
    blue = QtGui.QColor(42, 130, 218)

    # Window text
    palette.setColor(QtGui.QPalette.Window, dark_gray)
    palette.setColor(QtGui.QPalette.WindowText, Qt.white)
    
    # Base (text input backgrounds, etc.)
    palette.setColor(QtGui.QPalette.Base, black)
    palette.setColor(QtGui.QPalette.AlternateBase, dark_gray)
    
    # Tooltips
    palette.setColor(QtGui.QPalette.ToolTipBase, black)
    palette.setColor(QtGui.QPalette.ToolTipText, Qt.white)
    
    # Text
    palette.setColor(QtGui.QPalette.Text, Qt.white)
    
    # Buttons
    palette.setColor(QtGui.QPalette.Button, dark_gray)
    palette.setColor(QtGui.QPalette.ButtonText, Qt.white)
    palette.setColor(QtGui.QPalette.BrightText, Qt.red)
    
    # Links
    palette.setColor(QtGui.QPalette.Link, blue)
    palette.setColor(QtGui.QPalette.Highlight, blue)
    palette.setColor(QtGui.QPalette.HighlightedText, Qt.black)

    # Disabled
    palette.setColor(QtGui.QPalette.Disabled, QtGui.QPalette.Text, gray)
    palette.setColor(QtGui.QPalette.Disabled, QtGui.QPalette.ButtonText, gray)
    palette.setColor(QtGui.QPalette.Disabled, QtGui.QPalette.WindowText, gray)

    app.setPalette(palette)
