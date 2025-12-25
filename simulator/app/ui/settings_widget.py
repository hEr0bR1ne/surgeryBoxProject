"""
Settings Widget - Font and other application settings
"""

from PySide6.QtWidgets import (QFrame, QVBoxLayout, QHBoxLayout, QLabel, 
                               QComboBox, QPushButton, QGroupBox)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
import json
import os


class SettingsWidget(QFrame):
    """Settings widget for font and other preferences"""
    
    font_changed = Signal(str)  # Emits selected font name
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: white; border-radius: 8px; padding: 20px;")
        
        # Font options: (display_name, font_family)
        self.font_options = [
            ("Default (Segoe Print)", "Segoe Print"),
            ("Times New Roman", "Times New Roman"),
            ("Microsoft YaHei (微软雅黑)", "Microsoft YaHei"),
        ]
        
        self.config_path = os.path.join(os.path.dirname(__file__), "..", "..", "user_settings.json")
        self.current_font = "Segoe Print"
        
        self._setup_ui()
        self._load_settings()
    
    def _setup_ui(self):
        """Setup UI components"""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        title = QLabel("Settings")
        title.setFont(QFont("Segoe Print", 24, QFont.Bold))
        main_layout.addWidget(title)
        
        # Font Settings Group
        font_group = QGroupBox("Font Settings")
        font_group.setFont(QFont("Segoe Print", 12))
        font_layout = QVBoxLayout(font_group)
        
        # Font selection
        font_container = QHBoxLayout()
        font_label = QLabel("Select Font:")
        font_label.setFont(QFont("Segoe Print", 11))
        font_label.setMinimumWidth(120)
        
        self.font_combo = QComboBox()
        self.font_combo.setFont(QFont("Segoe Print", 11))
        self.font_combo.setMinimumWidth(300)
        self.font_combo.setMinimumHeight(40)
        
        # Add font options
        for display_name, font_family in self.font_options:
            self.font_combo.addItem(display_name, font_family)
        
        self.font_combo.currentIndexChanged.connect(self._on_font_changed)
        
        font_container.addWidget(font_label)
        font_container.addWidget(self.font_combo)
        font_container.addStretch()
        
        font_layout.addLayout(font_container)
        
        # Preview label
        preview_label = QLabel("Preview:")
        preview_label.setFont(QFont("Segoe Print", 11))
        
        self.preview_text = QLabel("The quick brown fox jumps over the lazy dog")
        self.preview_text.setFont(QFont("Segoe Print", 14))
        self.preview_text.setStyleSheet("background: #f0f0f0; padding: 15px; border-radius: 5px;")
        self.preview_text.setMinimumHeight(60)
        
        font_layout.addWidget(preview_label)
        font_layout.addWidget(self.preview_text)
        
        main_layout.addWidget(font_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        btn_apply = QPushButton("Apply")
        btn_apply.setFont(QFont("Segoe Print", 11))
        btn_apply.setMinimumSize(120, 40)
        btn_apply.setStyleSheet("""
            QPushButton {
                background: #4DA3FF;
                color: white;
                border: none;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #3a7bc8;
            }
        """)
        btn_apply.clicked.connect(self._apply_settings)
        
        button_layout.addWidget(btn_apply)
        main_layout.addLayout(button_layout)
        
        main_layout.addStretch()
    
    def _on_font_changed(self, index):
        """Update preview when font selection changes"""
        font_family = self.font_combo.itemData(index)
        self.current_font = font_family
        
        # Update preview
        preview_font = QFont(font_family, 14)
        self.preview_text.setFont(preview_font)
    
    def _apply_settings(self):
        """Apply settings and save to file"""
        self._save_settings()
        self.font_changed.emit(self.current_font)
    
    def _save_settings(self):
        """Save settings to JSON file"""
        settings = {
            "font": self.current_font
        }
        
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=4, ensure_ascii=False)
            print(f"[Settings] Saved to {self.config_path}: {settings}")
        except Exception as e:
            print(f"[Settings] Error saving settings: {e}")
    
    def _load_settings(self):
        """Load settings from JSON file"""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                    self.current_font = settings.get("font", "Segoe Print")
                    
                    # Set combo box to the loaded font
                    for i, (display_name, font_family) in enumerate(self.font_options):
                        if font_family == self.current_font:
                            self.font_combo.setCurrentIndex(i)
                            break
                    
                    print(f"[Settings] Loaded from {self.config_path}: {settings}")
        except Exception as e:
            print(f"[Settings] Error loading settings: {e}")
    
    def get_current_font(self):
        """Get the currently selected font family name"""
        return self.current_font
