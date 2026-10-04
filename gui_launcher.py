"""
MAYA Native Windows Desktop Launcher (PyQt6-WebEngine)
Launches the full desktop application window with native Windows frame, dark titlebar, and system tray.
"""
import sys
import os
import time

def launch_native_window():
    try:
        from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget
        from PyQt6.QtWebEngineWidgets import QWebEngineView
        from PyQt6.QtCore import QUrl
        from PyQt6.QtGui import QColor
    except ImportError:
        print("PyQt6 / PyQt6-WebEngine not available. Launching via Electron instead...")
        os.system("npm --prefix apps/desktop run electron")
        return

    app = QApplication(sys.argv)
    app.setApplicationName("Maya")

    window = QMainWindow()
    window.setWindowTitle("Maya — Personal AI Desktop Companion")
    window.resize(1366, 840)
    window.setMinimumSize(1100, 700)

    # Set dark window background
    palette = window.palette()
    palette.setColor(window.backgroundRole(), QColor("#070b14"))
    window.setPalette(palette)

    central_widget = QWidget(window)
    layout = QVBoxLayout(central_widget)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)

    web_view = QWebEngineView(central_widget)
    web_view.page().setBackgroundColor(QColor("#070b14"))

    dist_index = os.path.abspath(os.path.join(os.path.dirname(__file__), "apps", "desktop", "dist", "index.html"))
    if os.path.exists(dist_index):
        target_url = QUrl.fromLocalFile(dist_index)
    else:
        target_url = QUrl("http://127.0.0.1:5173")

    web_view.load(target_url)

    layout.addWidget(web_view)
    window.setCentralWidget(central_widget)
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    launch_native_window()
