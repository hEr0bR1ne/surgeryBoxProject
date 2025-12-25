from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap, QFont, QFontMetrics
from PySide6.QtWidgets import (
    QWidget, QLabel, QLineEdit, QPushButton,
    QVBoxLayout, QHBoxLayout, QFrame, QApplication
)

from types import SimpleNamespace

from app.config import APP_NAME
from app.auth import authenticate


class LoginPage(QWidget):
    logged_in = Signal(object)

    def __init__(self):
        super().__init__()
        self._setup_window()
        self._build_ui()

    # --------------------------------------------------
    # Window: real fullscreen (game style)
    # --------------------------------------------------
    def _setup_window(self):
        # Only make it a frameless fullscreen window when used standalone
        if self.parent() is None:
            self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
            self.showFullScreen()

    # --------------------------------------------------
    # UI
    # --------------------------------------------------
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        # ===== Background =====
        bg = QLabel()
        bg.setPixmap(QPixmap("assets/background.jpg"))
        bg.setScaledContents(True)
        root.addWidget(bg)

        # ===== Overlay =====
        self.overlay = QFrame(bg)
        self.overlay.setGeometry(self.rect())
        self.overlay.setStyleSheet("QFrame { background: rgba(255,255,255,0.25); }")

        overlay_l = QVBoxLayout(self.overlay)
        overlay_l.setContentsMargins(32, 24, 32, 24)

        # ===== Top bar =====
        top = QHBoxLayout()
        top.addStretch()

        exit_btn = QPushButton("Exit")
        exit_btn.setCursor(Qt.PointingHandCursor)
        f = QFont("Segoe Script", 20, QFont.Bold)
        f.setItalic(True)
        exit_btn.setFont(f)
        exit_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                color: #003366;
                font-family: 'Segoe Script', 'Brush Script MT', cursive;
                font-size: 20px;
            }
            QPushButton:hover {
                color: #001a33;
            }
        """)
        exit_btn.clicked.connect(QApplication.quit)
        top.addWidget(exit_btn)

        overlay_l.addLayout(top)
        overlay_l.addStretch(2)
        overlay_l.addSpacing(320)

        # ===== Login Card =====
        card = QFrame()
        card.setFixedWidth(420)
        card.setStyleSheet("""
            QFrame {
                background: rgba(255,255,255,0.4);
                border-radius: 20px;
            }
        """)

        card_l = QVBoxLayout(card)
        card_l.setContentsMargins(32, 32, 32, 32)
        card_l.setSpacing(18)

        # Title
        title = QLabel("Login")
        title.setAlignment(Qt.AlignCenter)
        f_title = QFont("Segoe Script", 28, QFont.Bold)
        f_title.setItalic(True)
        title.setFont(f_title)
        title.setStyleSheet("""
            color: #003366;
            font-family: 'Segoe Script', 'Brush Script MT', cursive;
            font-size: 28px;
        """)

        # Username
        self.user = QLineEdit()
        self.user.setPlaceholderText("Username")
        self._style_input(self.user)

        # Password
        self.pw = QLineEdit()
        self.pw.setPlaceholderText("Password")
        self.pw.setEchoMode(QLineEdit.Password)
        self._style_input(self.pw)

        # Error
        self.err = QLabel("")
        self.err.setVisible(False)
        self.err.setAlignment(Qt.AlignCenter)
        self.err.setStyleSheet("""
            QLabel {
                color: #d12b2b;
                font-size: 13px;
            }
        """)

        # Login button
        login_btn = QPushButton("Login")
        login_btn.setCursor(Qt.PointingHandCursor)
        login_btn.setFixedHeight(44)
        login_btn.setFont(QFont("Segoe UI", 15))
        login_btn.setStyleSheet("""
            QPushButton {
                background-color: #4da3ff;
                color: white;
                border-radius: 22px;
            }
            QPushButton:hover {
                background-color: #3b92ec;
            }
        """)
        login_btn.clicked.connect(self._do_login)

        # Assemble card
        card_l.addWidget(title)
        card_l.addSpacing(6)
        card_l.addWidget(self.user)
        card_l.addWidget(self.pw)
        card_l.addWidget(self.err)
        card_l.addSpacing(8)
        card_l.addWidget(login_btn)

        # Debug button to skip login (development convenience)
        debug_btn = QPushButton("Debug")
        debug_btn.setCursor(Qt.PointingHandCursor)
        debug_btn.setFixedHeight(36)
        debug_btn.setFont(QFont("Segoe Script", 14, QFont.Bold))
        debug_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                color: #003366;
                font-family: 'Segoe Script', 'Brush Script MT', cursive;
                font-size: 14px;
            }
            QPushButton:hover { color: #001a33; }
        """)
        debug_btn.clicked.connect(self._debug_login)
        card_l.addSpacing(6)
        card_l.addWidget(debug_btn)

        overlay_l.addWidget(card, alignment=Qt.AlignCenter)
        overlay_l.addStretch(3)

        # Keyboard
        self.user.returnPressed.connect(self._do_login)
        self.pw.returnPressed.connect(self._do_login)

    # --------------------------------------------------
    # Helpers
    # --------------------------------------------------
    def _style_input(self, w):
        w.setFixedHeight(42)
        w.setStyleSheet("""
            QLineEdit {
                border: 1px solid #cfe3ff;
                border-radius: 21px;
                padding-left: 14px;
                font-size: 14px;
            }
            QLineEdit:focus {
                border-color: #4da3ff;
            }
        """)
    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "overlay"):
            # keep overlay covering the full widget when resized (e.g., fullscreen)
            self.overlay.setGeometry(self.rect())

    def _debug_login(self):
        """Emit a debug user to bypass login (development helper)."""
        user = SimpleNamespace(username="debug", role="trainer")
        self.logged_in.emit(user)

    # --------------------------------------------------
    # Login logic
    # --------------------------------------------------
    def _do_login(self):
        u = self.user.text().strip()
        p = self.pw.text()

        user = authenticate(u, p)
        if not user:
            self.err.setText("Invalid username or password")
            self.err.setVisible(True)
            return

        self.err.setVisible(False)
        self.logged_in.emit(user)
