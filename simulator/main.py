#conda activate epidural310

import sys
from PySide6.QtWidgets import QApplication
from app.ui.main_window import App

def main():
    app = QApplication(sys.argv)
    win = App()
    from PySide6.QtCore import Qt
    win.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
    win.showFullScreen()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
