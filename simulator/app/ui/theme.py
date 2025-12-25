from dataclasses import dataclass
from app import config

@dataclass(frozen=True)
class Theme:
    name: str  # "light" | "dark"

def qss_for(theme: Theme) -> str:
    if theme.name == "dark":
        bg = config.BG_DARK
        fg = config.TEXT_LIGHT
        panel = "#121F2E"
        border = "#24364B"
        hover = "#1A2A3D"
        accent = config.PRIMARY_COLOR
    else:
        bg = config.BG_LIGHT
        fg = config.TEXT_DARK
        panel = "#FFFFFF"
        border = "#CFE3F7"
        hover = "#EEF6FF"
        accent = config.PRIMARY_COLOR

    return f"""
    QWidget {{
        background: {bg};
        color: {fg};
        font-family: "Segoe UI", Arial;
        font-size: 14px;
    }}
    QLineEdit {{
        background: {panel};
        border: 1px solid {border};
        border-radius: 10px;
        padding: 10px 12px;
    }}
    QPushButton {{
        background: {panel};
        border: 1px solid {border};
        border-radius: 12px;
        padding: 10px 14px;
    }}
    QPushButton:hover {{
        background: {hover};
    }}
    QPushButton#Primary {{
        background: {accent};
        color: white;
        border: 0px;
        font-weight: 600;
    }}
    QPushButton#Primary:hover {{
        opacity: 0.92;
    }}
    QLabel#Title {{
        font-size: 18px;
        font-weight: 700;
    }}
    QLabel#Header {{
        font-size: 16px;
        font-weight: 700;
    }}
    QFrame#Card {{
        background: {panel};
        border: 1px solid {border};
        border-radius: 16px;
    }}
    """
