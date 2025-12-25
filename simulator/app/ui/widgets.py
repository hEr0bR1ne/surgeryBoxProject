from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QPixmap, QColor
from PySide6.QtWidgets import QLabel

def logo_placeholder(size: QSize) -> QLabel:
    """
    v0.1: 纯色占位 logo
    """
    pix = QPixmap(size)
    pix.fill(QColor("#4DA3FF"))
    lab = QLabel()
    lab.setPixmap(pix)
    lab.setFixedSize(size)
    lab.setScaledContents(True)
    lab.setStyleSheet("border-radius: 10px;")
    return lab

def section_placeholder(title: str) -> QLabel:
    lab = QLabel(title)
    lab.setAlignment(Qt.AlignCenter)
    lab.setStyleSheet("QLabel{font-size:16px;font-weight:700;}")
    return lab
