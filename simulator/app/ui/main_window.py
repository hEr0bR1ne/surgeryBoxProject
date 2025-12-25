from PySide6.QtCore import Qt, QUrl, QTimer
from PySide6.QtWidgets import (
    QWidget, QMainWindow, QStackedWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QLabel, QFrame, QListWidget, QListWidgetItem, QSlider, QComboBox,
    QTextEdit, QScrollArea
)
from PySide6.QtGui import QFont, QPixmap

# Multimedia for background music and click sounds
try:
    from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput, QMediaPlaylist, QSoundEffect
    from PySide6.QtMultimediaWidgets import QVideoWidget
except Exception:
    # Some PySide6 builds may not provide QMediaPlaylist; fallback gracefully
    try:
        from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput, QSoundEffect
        from PySide6.QtMultimediaWidgets import QVideoWidget
        QMediaPlaylist = None
    except Exception:
        from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput, QSoundEffect
        QMediaPlaylist = None
        QVideoWidget = None

import os
import random
import json

from app.config import APP_NAME, APP_VERSION
from app.ui.login_page import LoginPage
from app.camera_manager import CameraManager
from app.hardware_connector import HardwareConnector, ConnectionTestThread
from app.ui.theme import Theme, qss_for
from app.ui.widgets import section_placeholder
from app.ui.settings_widget import SettingsWidget
from app.storage import write_profile_if_missing
from app.quiz_module import QuizModule

class App(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} - {APP_VERSION}")
        self.setMinimumSize(1100, 700)  # 适配横屏平板与笔记本

        self.theme = Theme("light")
        self.setStyleSheet(qss_for(self.theme))

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        # Login as first widget
        self.login = LoginPage()
        self.login.logged_in.connect(self._on_login)
        self.stack.addWidget(self.login)

        self.main = None
        self.stack.setCurrentWidget(self.login)

    def _on_login(self, user):
        write_profile_if_missing(user.username, user.role)

        # When logged in, initialize main shell and start welcome behavior
        self.main = MainShell(user=user, on_logout=self._logout, on_toggle_theme=self._toggle_theme)
        self.stack.addWidget(self.main)
        self.stack.setCurrentWidget(self.main)

        # Start welcome behaviors (music & quote)
        self.main.start_welcome()


    def _logout(self):
        # Clean up camera manager if it exists
        if hasattr(self, 'main') and self.main and hasattr(self.main, 'camera_manager_widget'):
            try:
                self.main.camera_manager_widget.cleanup()
            except Exception:
                pass
        
        # Stop music playback completely before returning to login
        if hasattr(self, 'main') and self.main and hasattr(self.main, 'music_player'):
            if self.main.music_player:
                try:
                    self.main.music_player.stop()
                    # Also ensure volume is muted
                    if hasattr(self.main, 'music_audio_output') and self.main.music_audio_output:
                        self.main.music_audio_output.setVolume(0.0)
                except Exception:
                    pass
        self.stack.setCurrentWidget(self.login)

    def _toggle_theme(self):
        self.theme = Theme("dark" if self.theme.name == "light" else "light")
        self.setStyleSheet(qss_for(self.theme))

class MainShell(QWidget):
    # Placeholder quotes - replace the strings below with your 5 short nursing quotes
    QUOTES = [
        "The most important practical lesson that can be given to nurses is to teach them what to observe.",
        "Nursing is an art: and if it is to be made an art, it requires as exclusive a devotion as any painter’s or sculptor’s work.",
        "Nursing is a profession, not a task.",
        "The nurse is the last line of defence.",
        "When in doubt, stop and escalate.",
    ]

    def __init__(self, user, on_logout, on_toggle_theme, parent=None):
        super().__init__(parent)
        # identify root widget for specific stylesheet overrides
        self.setObjectName("MainShell")
        self.user = user
        self.on_logout = on_logout
        self.on_toggle_theme = on_toggle_theme

        # --- click sound (default) ---
        self.click_sfx = QSoundEffect()
        click_path = os.path.join(os.getcwd(), 'assets', 'click.wav')
        if os.path.exists(click_path):
            self.click_sfx.setSource(QUrl.fromLocalFile(click_path))
        else:
            self.click_sfx = None

        # --- background music setup (will be started by start_welcome) ---
        music_path = os.path.join(os.getcwd(), 'assets', 'background.mp3')
        self.music_player = None
        if os.path.exists(music_path):
            try:
                self.music_player = QMediaPlayer()
                self.music_audio_output = QAudioOutput()
                self.music_player.setAudioOutput(self.music_audio_output)
                self.music_audio_output.setVolume(0.2)

                # Prefer QMediaPlaylist when available; otherwise set source and loop manually
                if QMediaPlaylist is not None:
                    self.music_playlist = QMediaPlaylist()
                    self.music_playlist.addMedia(QUrl.fromLocalFile(music_path))
                    self.music_playlist.setPlaybackMode(QMediaPlaylist.Loop)
                    self.music_player.setPlaylist(self.music_playlist)
                else:
                    # Fallback: set source and reconnect on stop to loop
                    self.music_player.setSource(QUrl.fromLocalFile(music_path))
                    try:
                        self.music_player.playbackStateChanged.connect(self._on_music_state_changed)
                    except Exception:
                        # older/newer bindings may use different signal names; ignore if unavailable
                        pass
            except Exception:
                self.music_player = None
        else:
            self.music_player = None

        # Background image for main shell (if provided). Use a QLabel so it is visible despite app-wide QWidget styles.
        bg_path = os.path.join(os.getcwd(), 'assets', 'backgroundMain.jpg')
        if not os.path.exists(bg_path):
            fb = os.path.join(os.getcwd(), 'assets', 'background.jpg')
            if os.path.exists(fb):
                bg_path = fb
            else:
                bg_path = None

        self.bg = None
        if bg_path:
            try:
                pix = QPixmap(bg_path)
                if not pix.isNull():
                    self.bg = QLabel(self)
                    self.bg.setPixmap(pix)
                    self.bg.setScaledContents(True)
                    self.bg.setGeometry(self.rect())
                    self.bg.lower()  # send to back
            except Exception:
                self.bg = None

        # Ensure top/left/content use the hand-drawn font and blue color

        # Load and apply user's font preference
        self._load_and_apply_user_font()

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)
        # apply a default handwritten font (less cursive) to all child widgets
        try:
            self.setFont(QFont('Segoe Print', 16))
        except Exception:
            pass

        # Top bar (white translucent strip)
        top = QFrame()
        top.setObjectName("TopBar")
        top.setStyleSheet("background: rgba(255,255,255,0.6); border: none; border-radius: 12px;")
        top_l = QHBoxLayout(top)
        top_l.setContentsMargins(14, 10, 14, 10)
        top_l.setSpacing(10)

        left_title = QLabel(f"Simulation Training for Epidural Analgesia Nursing Care")
        left_title.setObjectName("Header")
        # enforce font, size and color via stylesheet to override theme QSS
        left_title.setStyleSheet("color: #003366; font-family: 'Segoe Print', 'Segoe UI', Arial; font-size: 25px; font-weight: 700; background: transparent; border: none; padding: 0;")

        top_l.addWidget(left_title)
        top_l.addStretch(1)

        # Language selector temporarily disabled
        # self.lang = QComboBox()
        # self.lang.addItems(["English", "中文（繁體）(dev)", "中文（简体）(dev)"])
        # self.lang.setStyleSheet("font-family: 'Segoe Script', cursive; font-size:14px;")
        # self.lang.currentIndexChanged.connect(lambda _: self._on_button_click(lambda: self._set_content("Language switching (dev)")))
        # top_l.addWidget(self.lang)

        # Reset Simulator button
        btn_reset_sim = QPushButton("Reset Simulator")
        btn_reset_sim.clicked.connect(lambda: self._on_button_click(self._reset_simulator))
        top_l.addWidget(btn_reset_sim)

        # Background music mute toggle (default: playing/unmuted) — simplified label
        self.btn_mute = QPushButton("Mute")
        self.btn_mute.setCheckable(True)
        self.btn_mute.clicked.connect(lambda: self._on_button_click(self._toggle_music))
        top_l.addWidget(self.btn_mute)

        # Simulator Connection Debug (new)
        btn_sim_conn = QPushButton("Simulator")
        btn_sim_conn.clicked.connect(lambda: self._on_button_click(self._show_simulator_connection))
        top_l.addWidget(btn_sim_conn)

        # Settings (placeholder)
        btn_settings = QPushButton("Settings")
        btn_settings.clicked.connect(lambda: self._on_button_click(self._show_settings))
        top_l.addWidget(btn_settings)

        # Logout
        btn_logout = QPushButton(f"Logout ({self.user.username})")
        btn_logout.clicked.connect(lambda: self._on_button_click(self.on_logout))
        top_l.addWidget(btn_logout)

        # Unified button style (boxed look)
        btn_style = """
            QPushButton {
                background: rgba(255,255,255,0.6);
                border: 1px solid rgba(0,0,0,0.06);
                padding: 6px 10px;
                border-radius: 8px;
                font-family: 'Segoe Print', 'Segoe UI', Arial;
                font-size: 16px;
                color: #003366;
            }
            QPushButton:hover {
                background: rgba(255,255,255,0.75);
            }
            QPushButton:pressed {
                background: rgba(0,0,0,0.08);
            }
        """
        for w in top.findChildren(QPushButton):
            w.setStyleSheet(btn_style)

        # Apply main shell handwritten font + color globally
        try:
            existing = self.styleSheet() or ""
            existing += f"\n#{self.objectName()} {{ font-family: 'Segoe Script', cursive; color: #003366; }}"
            self.setStyleSheet(existing)
        except Exception:
            pass

        root.addWidget(top)

        # Body: left menu + content
        body = QHBoxLayout()
        body.setSpacing(12)

        # Left menu
        menu = QFrame()
        menu.setObjectName("Card")
        menu.setStyleSheet("background: rgba(255,255,255,0.85);")
        menu_l = QVBoxLayout(menu)
        menu_l.setContentsMargins(10, 10, 10, 10)
        menu_l.setSpacing(8)

        self.menu_list = QListWidget()
        self.menu_list.setStyleSheet("QListWidget{border:0px; background: transparent;} QListWidget::item{padding:12px;border-radius:10px; color: #003366;}")
        self.menu_list.setFont(QFont('Segoe Script', 12))

        items = [
            ("Welcome", "welcome"),
            ("Simulation Training", "simulation"),
            ("E-learning Module", "elearning"),
            ("Practice Questions", "practice"),
            ("Practice Records", "practice_records"),
            ("Training Records", "training_records"),
            ("AI Nursing Mentor", "ai_mentor"),  # 新增AI对话菜单
            # ("Report Records", "reports"),
        ]
        if self.user.role == "trainer":
            items.append(("Trainer Dashboard", "dashboard"))

        for text, key in items:
            it = QListWidgetItem(text)
            it.setData(Qt.UserRole, key)

            it.setFont(QFont('Segoe Print', 14))
            self.menu_list.addItem(it)

        self.menu_list.currentItemChanged.connect(self._on_menu)
        # Start with Welcome selected (index 0)
        self.menu_list.setCurrentRow(0)

        lbl_modules = QLabel("Modules")
        lbl_modules.setObjectName("ModulesLabel")
        lbl_modules.setFont(QFont('Segoe Print', 22, QFont.Bold))
        lbl_modules.setStyleSheet("color: #003366; font-family: 'Segoe Print', 'Segoe UI', Arial; font-size: 26px; font-weight: 700;")
        menu_l.addWidget(lbl_modules)

        # menu list style: transparent bg; items styled as button-like with selection state using Segoe Print
        self.menu_list.setStyleSheet("""
            QListWidget{border:0px; background: transparent;}
            QListWidget::item{padding:14px;border-radius:10px; color: #003366; font-family: 'Segoe Print', 'Segoe UI', Arial; font-size:20px;}
            QListWidget::item:selected{background: rgba(77,163,255,0.12); border-left:4px solid #4DA3FF; color: #003366; font-weight:700;}
        """)
        self.menu_list.setSelectionMode(QListWidget.SingleSelection)
        menu_l.addWidget(self.menu_list)

        # ensure MainShell-local override for Modules label so theme can't override it
        try:
            existing = self.styleSheet() or ""
            existing += f"\n#{self.objectName()} QLabel#ModulesLabel {{ font-family: 'Segoe Print', 'Segoe UI', Arial; font-size: 28px; font-weight:700; color: #003366; }}"
            self.setStyleSheet(existing)
        except Exception:
            pass

        menu.setFixedWidth(260)
        body.addWidget(menu)

        # Content area
        self.content = QFrame()
        self.content.setObjectName("Card")
        # keep the content slightly translucent to show background image (less transparent now)
        self.content.setStyleSheet("background: rgba(255,255,255,0.8);")
        content_l = QVBoxLayout(self.content)
        content_l.setContentsMargins(18, 18, 18, 18)
        content_l.setSpacing(12)

        self.content_title = QLabel("")
        self.content_title.setObjectName("Header")
        self.content_title.setFont(QFont('Segoe Print', 28, QFont.Bold))
        # enforce font-family & size via stylesheet so it is not overridden by theme QSS
        self.content_title.setStyleSheet("color: #003366; background: transparent; font-family: 'Segoe Print', 'Segoe UI', Arial; font-size: 30px; font-weight:700;")
        self.content_title.setVisible(False)

        self.content_view = QLabel("")
        self.content_view.setAlignment(Qt.AlignCenter)
        self.content_view.setWordWrap(True)
        self.content_view.setStyleSheet("QLabel{font-size:18px;opacity:0.95; font-family: 'Segoe Print', 'Segoe UI', Arial; color:#003366; background: transparent;}")
        self.content_view.setVisible(False)

        # quote label centered and larger (kept for generic use)
        self.quote_label = QLabel("")
        self.quote_label.setStyleSheet("font-family: 'Segoe Print', 'Brush Script MT', cursive; color:#234f8d; font-size:32px; background: transparent;")
        self.quote_label.setAlignment(Qt.AlignCenter)
        self.quote_label.setWordWrap(True)

        # welcome_quote: larger, placed center-right of bottom area; visible on Welcome
        self.welcome_quote = QLabel("")
        self.welcome_quote.setStyleSheet("font-family: 'Segoe Print', 'Brush Script MT', cursive; color:#234f8d; font-size:26px; background: transparent;")
        self.welcome_quote.setWordWrap(True)
        self.welcome_quote.setAlignment(Qt.AlignCenter)
        self.welcome_quote.setVisible(False)  # will be shown when Welcome is selected

        content_l.addWidget(self.content_title)
        content_l.addStretch(1)
        content_l.addWidget(self.content_view)
        content_l.addStretch(1)
        # welcome_quote: fill width and positioned higher
        content_l.addWidget(self.welcome_quote)
        content_l.addStretch(2)

        body.addWidget(self.content, stretch=1)
        root.addLayout(body, stretch=1)

        # default content: trigger welcome on startup (delayed to avoid accessing incomplete objects)
        # Use QTimer to defer the call until after initialization completes
        QTimer.singleShot(300, self._init_welcome)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # keep background covering the full widget
        try:
            if hasattr(self, 'bg') and self.bg:
                self.bg.setGeometry(self.rect())
        except Exception:
            pass

    def _init_welcome(self):
        """Initialize welcome page after full setup."""
        try:
            # Verify all required attributes exist
            if not hasattr(self, 'welcome_quote'):
                print("Warning: welcome_quote not yet initialized")
                QTimer.singleShot(200, self._init_welcome)  # Retry
                return
            
            welcome_item = self.menu_list.item(0)
            if welcome_item:
                self._on_menu(welcome_item, None)
        except Exception as e:
            print(f"Error in _init_welcome: {e}")
            # Retry after another delay
            QTimer.singleShot(200, self._init_welcome)

    def _on_music_state_changed(self, state):
        # Fallback loop helper when QMediaPlaylist isn't available
        try:
            if state == QMediaPlayer.StoppedState and self.music_player is not None:
                self.music_player.setPosition(0)
                self.music_player.play()
        except Exception:
            pass

    # Helper that plays click sound (if any) and then performs callback
    def _on_button_click(self, callback):
        if self.click_sfx:
            try:
                self.click_sfx.play()
            except Exception:
                pass
        if callable(callback):
            callback()

    def _toggle_music(self):
        if not self.music_player:
            return
        # prefer toggling audio output volume (more reliable across backends)
        try:
            # if we have an audio output, mute by dropping volume to 0 and remember previous
            ao = getattr(self, 'music_audio_output', None)
            if ao is not None:
                current = ao.volume()
                if getattr(self, '_prev_volume', None) is None or current > 0:
                    # mute
                    self._prev_volume = current
                    ao.setVolume(0.0)
                    self.btn_mute.setChecked(True)
                else:
                    # unmute: restore
                    ao.setVolume(getattr(self, '_prev_volume', 0.2))
                    self.btn_mute.setChecked(False)
            else:
                # fallback to QMediaPlayer.muted
                muted = self.music_player.isMuted()
                self.music_player.setMuted(not muted)
                self.btn_mute.setChecked(not muted)
        except Exception:
            pass

    def _reset_simulator(self):
        """Send reset command to simulator hardware"""
        try:
            connector = HardwareConnector()
            success, message = connector.send_command("reset")
            if success:
                # Show success message in status bar or notification
                print(f"[MainWindow] Simulator reset: {message}")
            else:
                print(f"[MainWindow] Simulator reset failed: {message}")
        except Exception as e:
            print(f"[MainWindow] Error resetting simulator: {str(e)}")

    def _load_and_apply_user_font(self):
        """Load user's saved font preference and apply it"""
        try:
            import json
            config_path = os.path.join(os.path.dirname(__file__), "..", "..", "user_settings.json")
            
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                    font_name = settings.get("font", "Segoe Print")
                    print(f"[Settings] Loaded user font: {font_name}")
                    
                    # Apply font to entire MainShell
                    self._apply_font_recursively(self, font_name)
        except Exception as e:
            print(f"[Settings] Error loading user font: {e}")
    
    def _apply_font_recursively(self, widget, font_name):
        """Recursively apply font to widget and all children"""
        # Get current font size for this widget
        current_font = widget.font()
        size = current_font.pointSize() if current_font.pointSize() > 0 else 11
        weight = current_font.weight()
        
        # Apply new font with same size and weight
        new_font = QFont(font_name, size)
        new_font.setWeight(weight)
        widget.setFont(new_font)
        
        # Recursively apply to children
        for child in widget.findChildren(QWidget):
            current_font = child.font()
            size = current_font.pointSize() if current_font.pointSize() > 0 else 11
            weight = current_font.weight()
            
            new_font = QFont(font_name, size)
            new_font.setWeight(weight)
            child.setFont(new_font)
    
    def _apply_font_globally(self, font_name):
        """Apply selected font to all UI elements in MainShell"""
        print(f"[Settings] Applying font to MainShell: {font_name}")
        self._apply_font_recursively(self, font_name)
        print(f"[Settings] Font applied successfully")
    
    def start_welcome(self):
        # Play music (if available)
        if self.music_player:
            try:
                self.music_player.play()
                self.music_player.setMuted(False)
                self.btn_mute.setChecked(False)
            except Exception:
                pass

    def _on_training_button_click(self, training_key: str):
        """处理训练按钮点击"""
        print(f"\n[MainWindow] _on_training_button_click called with key: {training_key}")
        
        # 播放点击音效
        if self.click_sfx:
            try:
                self.click_sfx.play()
            except Exception as e:
                print(f"Error playing click sound: {e}")
        
        # 根据类型启动对应的训练
        if training_key in ["remove_needle", "remove_needle_simulator", "remove_needle_no_simulator"]:
            print(f"[MainWindow] Starting remove_needle training with key: {training_key}")
            self._start_remove_needle_training(training_key)
        elif training_key == "change_dressing":
            print(f"[MainWindow] Starting change_dressing training")
            self._start_change_dressing_training()
        elif training_key == "comprehensive":
            print(f"[MainWindow] Starting comprehensive training")
            self._start_comprehensive_training()
        else:
            print(f"[MainWindow] Unknown training key: {training_key}")
    
    def _start_remove_needle_training(self, training_key: str = "remove_needle_no_simulator"):
        """启动拔针训练"""
        print(f"\n[Training] Entering _start_remove_needle_training with key: {training_key}")
        try:
            print(f"[Training] Importing RemoveNeedleTraining...")
            from app.training_remove_needle import RemoveNeedleTraining
            print(f"[Training] Import successful")
            
            # 清除菜单栏选中
            print(f"[Training] Clearing menu selection")
            self.menu_list.clearSelection()
            
            # 隐藏当前内容
            print(f"[Training] Hiding current content")
            if hasattr(self, 'simulation_container'):
                self.simulation_container.setVisible(False)
            self.welcome_quote.setVisible(False)
            self.content_title.setVisible(False)
            self.content_view.setVisible(False)
            
            # 创建训练模块作为content的直接子widget（不添加到layout）
            print(f"[Training] Creating RemoveNeedleTraining widget")
            print(f"[Training] self.content = {self.content}, type = {type(self.content)}")
            self.current_training = RemoveNeedleTraining(self.content, training_mode=training_key)
            # 传入用户名用于保存训练记录
            self.current_training.current_user = self.user.username
            print(f"[Training] RemoveNeedleTraining created successfully")
            
            print(f"[Training] Connecting training_completed signal")
            self.current_training.training_completed.connect(self._on_training_completed)
            
            print(f"[Training] Connecting quiz_triggered signal")
            self.current_training.quiz_triggered.connect(self._on_quiz_triggered_from_training)
            
            # 初始化quiz_module用于训练模式
            print(f"[Training] Initializing quiz_module for training mode")
            if not hasattr(self, 'quiz_module') or self.quiz_module is None:
                self.quiz_module = QuizModule(training_mode=True)
                quiz_path = os.path.join("assets", "epidural_quiz_questions.json")
                self.quiz_module.load_quiz_data(quiz_path)
                self.quiz_module.quiz_completed.connect(self._on_quiz_completed)
                self.quiz_module.back_clicked.connect(self._on_quiz_back)
                # 添加到content中，初始时隐藏
                content_l = self.content.layout()
                content_l.insertWidget(2, self.quiz_module)
                self.quiz_module.setVisible(False)
            
            # 设置训练widget占满整个content区域
            print(f"[Training] Setting training widget geometry to fill content")
            self.current_training.setGeometry(self.content.rect())
            
            # 使训练widget可见
            print(f"[Training] Setting training widget visible")
            self.current_training.setVisible(True)
            
            # 开始训练
            print(f"[Training] Calling start_training()")
            self.current_training.start_training()
            print(f"[Training] Training started successfully!")
        except Exception as e:
            import traceback
            print(f"\n[ERROR] Error starting remove needle training: {e}")
            print(traceback.format_exc())
    
    def _start_change_dressing_training(self):
        """启动更换敷料训练"""
        # TODO: 实现更换敷料训练
        print("Change dressing training not yet implemented")
    
    def _start_comprehensive_training(self):
        """启动综合训练"""
        # TODO: 实现综合训练（组合多个模块）
        print("Comprehensive training not yet implemented")
    
    def _on_quiz_triggered_from_training(self, question_id):
        """
        从训练中触发的Quiz（Q3, Q4, Q5）
        显示透明的Quiz浮在训练画面上，暂停Phase 4的拔针操作
        """
        try:
            print(f"[Training] Quiz triggered during training: {question_id}")
            
            # 暂停Phase 4的拔针操作
            if hasattr(self, 'current_training') and self.current_training:
                self.current_training.pause_phase4()
            
            if not hasattr(self, 'quiz_module') or self.quiz_module is None:
                print(f"[Training] Quiz module not initialized, creating now...")
                self.quiz_module = QuizModule(training_mode=True)
                quiz_path = os.path.join("assets", "epidural_quiz_questions.json")
                self.quiz_module.load_quiz_data(quiz_path)
                self.quiz_module.quiz_completed.connect(self._on_quiz_completed)
                self.quiz_module.back_clicked.connect(self._on_quiz_back)
                # 添加到content中
                if hasattr(self, 'content') and self.content.layout():
                    content_l = self.content.layout()
                    content_l.insertWidget(2, self.quiz_module)
            
            # 验证问题是否存在
            if not self.quiz_module.questions:
                print(f"[Training] Quiz module has no questions loaded!")
                return
                
            if question_id not in self.quiz_module.questions:
                print(f"[Training] Question {question_id} not found in loaded questions")
                print(f"[Training] Available questions: {list(self.quiz_module.questions.keys())}")
                return
            
            # 确保quiz_module可见并在最前
            if not self.quiz_module.isVisible():
                self.quiz_module.setVisible(True)
            self.quiz_module.raise_()
            self.quiz_module.activateWindow()
            
            # 设置半透明棕色背景，使quiz能够浮在训练画面上
            self.quiz_module.setStyleSheet("""
                QFrame {
                    background: rgba(101, 67, 33, 200);
                    border-radius: 8px;
                }
            """)
            
            # 启动特定的question
            print(f"[Training] Starting quiz with question: {question_id}")
            self.quiz_module.start_quiz([question_id])
            # remember which training quiz is pending so we can record result later
            try:
                self._pending_training_quiz_id = question_id
            except Exception:
                self._pending_training_quiz_id = None
            
        except Exception as e:
            import traceback
            print(f"[Training] Error triggering quiz: {e}")
            print(traceback.format_exc())
    
    def _on_training_completed(self):
        """训练完成"""
        try:
            print(f"[Training] Training completed, cleaning up")
            # 清理当前训练模块
            if hasattr(self, 'current_training') and self.current_training:
                self.current_training.setVisible(False)
                self.current_training.deleteLater()
                self.current_training = None
            
            # 显示训练选项
            print(f"[Training] Showing simulation options")
            self._show_simulation_options()
        except Exception as e:
            print(f"[Training] Error in training completion: {e}")
    
    def _stop_current_training(self):
        """停止当前的训练（菜单切换或按钮点击时调用）"""
        if hasattr(self, 'current_training') and self.current_training:
            try:
                self.current_training.cleanup()
                self.current_training.setVisible(False)
                self.current_training.deleteLater()
                self.current_training = None
            except Exception as e:
                print(f"Error stopping training: {e}")
    
    def _on_menu(self, current, _prev):
        """处理菜单项切换"""
        # 首先停止任何正在进行的训练
        self._stop_current_training()
        
        # 清理E-learning视频播放器
        self._cleanup_elearning_video()
        
        # 清理Practice相关容器
        self._cleanup_practice_containers()
        
        # 清理Practice Records容器
        self._cleanup_practice_records()
        
        # 清理Training Records容器
        self._cleanup_training_records()
        # 隐藏所有特殊内容容器（确保 AI Mentor 等被隐藏并清空）
        try:
            self._hide_all_content_containers()
        except Exception:
            pass
        
        if not current:
            return
        # small click sound when switching menu
        if self.click_sfx:
            try:
                self.click_sfx.play()
            except Exception:
                pass
        key = current.data(Qt.UserRole)
        
        # Always cleanup camera when switching away from settings
        if hasattr(self, 'camera_manager_widget') and key != "settings":
            self.camera_manager_widget.setVisible(False)
            try:
                self.camera_manager_widget.cleanup()
            except Exception:
                pass
        
        # Hide all special containers for non-special items
        if hasattr(self, 'simulation_container'):
            self.simulation_container.setVisible(False)
        if hasattr(self, 'simulator_conn_widget'):
            self.simulator_conn_widget.setVisible(False)
        
        if key == "welcome":
            # Verify welcome_quote exists before using it
            if not hasattr(self, 'welcome_quote'):
                print("Warning: welcome_quote not initialized yet")
                return
            
            # show a large quote centered in content area
            q = random.choice(self.QUOTES)
            self.welcome_quote.setText(q)
            self.welcome_quote.setVisible(True)
            # hide other content
            self.content_title.setVisible(False)
            self.content_view.setVisible(False)
            return
        elif key == "simulation":
            # Show three training option buttons
            self._show_simulation_options()
            return
        else:
            # hide welcome quote; show content title/view
            self.welcome_quote.setVisible(False)
            self.content_title.setVisible(True)
            
            # Special handling for E-learning
            if key == "elearning":
                self._show_elearning_content()
                return
            
            # Special handling for Practice
            if key == "practice":
                self._show_practice_options()
                return
            
            # Special handling for Practice Records
            if key == "practice_records":
                self._show_practice_records()
                return
            
            # Special handling for Training Records
            if key == "training_records":
                self._show_training_records()
                return
            
            # Special handling for AI Nursing Mentor
            if key == "ai_mentor":
                self._show_ai_mentor()
                return
            
            self.content_view.setVisible(True)

        mapping = {
            "reports": "Report Records (placeholder)\n- Per-user local reports",
            "dashboard": "Trainer Dashboard (placeholder)\n- Statistics view (trainer only)",
        }
        self._set_content(mapping.get(key, "Coming soon"))

    def _set_content(self, text: str):
        self.content_title.setText(text.splitlines()[0])
        self.content_view.setText(text)

    def _show_elearning_content(self):
        """Show E-learning module with video player."""
        # 隐藏所有其他内容容器
        self._hide_all_content_containers()
        
        # Hide content_view (text placeholder)
        self.content_view.setVisible(False)
        
        # Set title
        self.content_title.setText("E-learning Module")
        self.content_title.setVisible(True)
        
        # Create E-learning container if not exists
        if not hasattr(self, 'elearning_container'):
            self.elearning_container = QFrame()
            self.elearning_container.setStyleSheet("background: transparent;")
            layout = QVBoxLayout(self.elearning_container)
            layout.setSpacing(8)
            layout.setContentsMargins(0, 0, 0, 0)
            
            # Video section - create thumbnail view (left-aligned)
            video_section = QFrame()
            video_section.setStyleSheet("background: transparent;")
            video_layout = QVBoxLayout(video_section)
            video_layout.setSpacing(8)
            video_layout.setContentsMargins(0, 0, 0, 0)
            
            # Video title
            video_title = QLabel("Medical Dressing Tutorial")
            video_title.setStyleSheet("""
                font-family: 'Segoe Print', 'Segoe UI', Arial;
                font-size: 18px;
                font-weight: 700;
                color: #003366;
            """)
            video_layout.addWidget(video_title)
            
            # Video thumbnail placeholder (clickable) - 2/3 size
            self.video_thumbnail = QPushButton()
            thumbnail_width = 400  # 2/3 of 600
            thumbnail_height = 225  # Maintain 16:9 ratio
            self.video_thumbnail.setFixedSize(thumbnail_width, thumbnail_height)
            self.video_thumbnail.setStyleSheet("""
                QPushButton {
                    background: #000000;
                    border: 2px solid #4DA3FF;
                    border-radius: 8px;
                    padding: 0px;
                }
                QPushButton:hover {
                    border: 2px solid #234f8d;
                    background: #1a1a1a;
                }
            """)
            
            # Load and display video thumbnail (first frame)
            video_path = os.path.join("assets", "medicaldressing.mp4")
            if os.path.exists(video_path):
                # Try to capture first frame as thumbnail
                try:
                    import cv2
                    cap = cv2.VideoCapture(video_path)
                    ret, frame = cap.read()
                    if ret:
                        # Convert to RGB
                        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        # Resize to thumbnail size maintaining aspect ratio
                        h, w = frame_rgb.shape[:2]
                        aspect = w / h
                        target_aspect = thumbnail_width / thumbnail_height  # 16:9
                        
                        if aspect > target_aspect:
                            # Image is wider, fit by height
                            new_h = thumbnail_height
                            new_w = int(thumbnail_height * aspect)
                        else:
                            # Image is taller, fit by width
                            new_w = thumbnail_width
                            new_h = int(thumbnail_width / aspect)
                        
                        frame_rgb = cv2.resize(frame_rgb, (new_w, new_h))
                        
                        # Center crop to target size
                        y_offset = (new_h - thumbnail_height) // 2
                        x_offset = (new_w - thumbnail_width) // 2
                        frame_rgb = frame_rgb[y_offset:y_offset+thumbnail_height, x_offset:x_offset+thumbnail_width]
                        
                        # Convert to QPixmap
                        from PySide6.QtGui import QImage
                        h, w, ch = frame_rgb.shape
                        bytes_per_line = 3 * w
                        qt_image = QImage(frame_rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
                        pixmap = QPixmap.fromImage(qt_image)
                        
                        self.video_thumbnail.setIcon(pixmap)
                        self.video_thumbnail.setIconSize(pixmap.size())
                    cap.release()
                except Exception as e:
                    # Fallback: just show black button with play icon
                    self.video_thumbnail.setText("▶ Click to Play")
                    self.video_thumbnail.setStyleSheet("""
                        QPushButton {
                            background: #000000;
                            border: 2px solid #4DA3FF;
                            border-radius: 8px;
                            padding: 0px;
                            color: #FFFFFF;
                            font-size: 48px;
                            font-weight: 700;
                        }
                        QPushButton:hover {
                            border: 2px solid #234f8d;
                            background: #1a1a1a;
                        }
                    """)
            else:
                self.video_thumbnail.setText("▶ Click to Play")
                self.video_thumbnail.setStyleSheet("""
                    QPushButton {
                        background: #000000;
                        border: 2px solid #4DA3FF;
                        border-radius: 8px;
                        padding: 0px;
                        color: #FFFFFF;
                        font-size: 48px;
                        font-weight: 700;
                    }
                    QPushButton:hover {
                        border: 2px solid #234f8d;
                        background: #1a1a1a;
                    }
                """)
            
            self.video_thumbnail.clicked.connect(self._play_elearning_video)
            video_layout.addWidget(self.video_thumbnail, alignment=Qt.AlignLeft)
            video_layout.addStretch()
            
            layout.addWidget(video_section)
            
            # Learning Materials button
            materials_button_container = QFrame()
            materials_button_container.setStyleSheet("background: transparent;")
            materials_button_layout = QHBoxLayout(materials_button_container)
            materials_button_layout.setSpacing(12)
            materials_button_layout.setContentsMargins(0, 0, 0, 0)
            
            btn_learning_materials = QPushButton("Learning Materials")
            btn_learning_materials.setStyleSheet("""
                QPushButton {
                    background: rgba(77, 163, 255, 0.2);
                    border: 2px solid #4DA3FF;
                    border-radius: 8px;
                    padding: 12px;
                    font-family: 'Segoe Print', 'Segoe UI', Arial;
                    font-size: 16px;
                    font-weight: 600;
                    color: #003366;
                    min-height: 50px;
                    min-width: 200px;
                }
                QPushButton:hover {
                    background: rgba(77, 163, 255, 0.3);
                    border: 2px solid #234f8d;
                }
                QPushButton:pressed {
                    background: rgba(77, 163, 255, 0.4);
                }
            """)
            btn_learning_materials.clicked.connect(self._show_learning_materials)
            materials_button_layout.addWidget(btn_learning_materials, alignment=Qt.AlignLeft)
            materials_button_layout.addStretch()
            
            layout.addWidget(materials_button_container)
            layout.addStretch()
            
            # Add to content area
            content_l = self.content.layout()
            content_l.insertWidget(2, self.elearning_container)
        
        self.elearning_container.setVisible(True)
    
    def _show_learning_materials(self):
        """Show learning materials from reading.md."""
        # Hide elearning container
        if hasattr(self, 'elearning_container'):
            self.elearning_container.setVisible(False)
        
        # Create learning materials container if not exists
        if not hasattr(self, 'learning_materials_container'):
            self.learning_materials_container = QFrame()
            self.learning_materials_container.setStyleSheet("background: transparent;")
            materials_layout = QVBoxLayout(self.learning_materials_container)
            materials_layout.setSpacing(12)
            materials_layout.setContentsMargins(0, 0, 0, 0)
            
            # Create scroll area for content
            scroll_area = QScrollArea()
            scroll_area.setStyleSheet("""
                QScrollArea {
                    background: transparent;
                    border: none;
                }
                QScrollBar:vertical {
                    background: rgba(200, 200, 200, 0.2);
                    width: 10px;
                    border-radius: 5px;
                }
                QScrollBar::handle:vertical {
                    background: rgba(77, 163, 255, 0.5);
                    border-radius: 5px;
                    min-height: 20px;
                }
                QScrollBar::handle:vertical:hover {
                    background: rgba(77, 163, 255, 0.7);
                }
            """)
            scroll_area.setWidgetResizable(True)
            scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            scroll_area.setMinimumHeight(500)
            
            # Content display (read-only text edit)
            self.txt_materials_content = QTextEdit()
            self.txt_materials_content.setReadOnly(True)
            self.txt_materials_content.setAlignment(Qt.AlignTop | Qt.AlignLeft)
            self.txt_materials_content.setStyleSheet("""
                QTextEdit {
                    font-family: 'Segoe Print', 'Segoe UI', Arial;
                    font-size: 14px;
                    color: #003366;
                    background: rgba(255, 255, 255, 0.5);
                    border: 2px solid rgba(77, 163, 255, 0.3);
                    border-radius: 8px;
                    padding: 12px;
                    line-height: 1.6;
                }
            """)
            scroll_area.setWidget(self.txt_materials_content)
            
            materials_layout.addWidget(scroll_area, 1)
            
            # Back button
            back_button_container = QFrame()
            back_button_container.setStyleSheet("background: transparent;")
            back_button_layout = QHBoxLayout(back_button_container)
            back_button_layout.setSpacing(12)
            back_button_layout.setContentsMargins(0, 0, 0, 0)
            
            btn_back = QPushButton("← Back")
            btn_back.setStyleSheet("""
                QPushButton {
                    background: rgba(200, 200, 200, 0.3);
                    border: 2px solid #999999;
                    border-radius: 8px;
                    padding: 10px;
                    font-family: 'Segoe Print', 'Segoe UI', Arial;
                    font-size: 14px;
                    font-weight: 600;
                    color: #003366;
                    min-width: 100px;
                }
                QPushButton:hover {
                    background: rgba(200, 200, 200, 0.4);
                }
                QPushButton:pressed {
                    background: rgba(200, 200, 200, 0.5);
                }
            """)
            btn_back.clicked.connect(self._return_from_learning_materials)
            back_button_layout.addWidget(btn_back, alignment=Qt.AlignLeft)
            back_button_layout.addStretch()
            
            materials_layout.addWidget(back_button_container)
            
            # Add to content area
            content_l = self.content.layout()
            content_l.insertWidget(2, self.learning_materials_container)
        
        # Load and display reading.md content
        reading_path = os.path.join("assets", "reading.md")
        if os.path.exists(reading_path):
            with open(reading_path, 'r', encoding='utf-8') as f:
                content = f.read()
                # Simple markdown formatting: convert headers to bold
                content = content.replace("### ", "")
                content = content.replace("## ", "")
                content = content.replace("# ", "")
                self.txt_materials_content.setText(content)
        else:
            self.txt_materials_content.setText("Learning materials not found.")
        
        # Scroll to top
        self.txt_materials_content.verticalScrollBar().setValue(0)
        
        self.learning_materials_container.setVisible(True)
    
    def _return_from_learning_materials(self):
        """Return from learning materials to elearning main view."""
        # Hide learning materials
        if hasattr(self, 'learning_materials_container'):
            self.learning_materials_container.setVisible(False)
        
        # Show elearning container
        if hasattr(self, 'elearning_container'):
            self.elearning_container.setVisible(True)
    
    def _play_elearning_video(self):
        """Play video in full-screen within content area."""
        video_path = os.path.join("assets", "medicaldressing.mp4")
        if not os.path.exists(video_path):
            return
        
        # Hide the thumbnail container
        if hasattr(self, 'elearning_container'):
            self.elearning_container.setVisible(False)
        
        # Create video player frame
        if not hasattr(self, 'elearning_video_player'):
            self.elearning_video_player = QFrame()
            self.elearning_video_player.setStyleSheet("background: #000000;")
            self.elearning_video_player.setMinimumHeight(500)  # Set minimum height for video display
            player_layout = QVBoxLayout(self.elearning_video_player)
            player_layout.setSpacing(0)
            player_layout.setContentsMargins(0, 0, 0, 0)
            
            # Video output widget - Use QVideoWidget if available
            if QVideoWidget is not None:
                self.video_output = QVideoWidget()
                self.video_output.setStyleSheet("background: #000000;")
            else:
                # Fallback if QVideoWidget not available
                self.video_output = QFrame()
                self.video_output.setStyleSheet("background: #000000;")
            
            player_layout.addWidget(self.video_output, 1)  # stretch=1 makes it fill available space
            
            # Control bar with exit button
            control_bar = QFrame()
            control_bar.setStyleSheet("background: rgba(0, 0, 0, 0.8);")
            control_layout = QHBoxLayout(control_bar)
            control_layout.setSpacing(8)
            control_layout.setContentsMargins(12, 8, 12, 8)
            
            # Play/Pause button
            self.btn_play_pause = QPushButton("⏸ Pause")
            self.btn_play_pause.setStyleSheet("""
                QPushButton {
                    background: rgba(77, 163, 255, 0.5);
                    border: 1px solid #4DA3FF;
                    border-radius: 4px;
                    padding: 6px 12px;
                    font-family: 'Segoe Print';
                    font-size: 14px;
                    color: #FFFFFF;
                    font-weight: 600;
                }
                QPushButton:hover { background: rgba(77, 163, 255, 0.7); }
                QPushButton:pressed { background: rgba(77, 163, 255, 0.9); }
            """)
            self.btn_play_pause.clicked.connect(self._toggle_video_playback)
            control_layout.addWidget(self.btn_play_pause)
            
            # Time display
            self.lbl_time = QLabel("00:00 / 00:00")
            self.lbl_time.setStyleSheet("""
                font-family: 'Segoe Print';
                font-size: 12px;
                color: #FFFFFF;
            """)
            control_layout.addWidget(self.lbl_time)
            
            # Time slider
            self.video_slider = QSlider(Qt.Horizontal)
            self.video_slider.setStyleSheet("""
                QSlider::groove:horizontal {
                    background: rgba(200, 200, 200, 0.3);
                    height: 6px;
                    border-radius: 3px;
                }
                QSlider::handle:horizontal {
                    background: #4DA3FF;
                    width: 12px;
                    margin: -3px 0;
                    border-radius: 6px;
                }
            """)
            self.video_slider.sliderMoved.connect(self._seek_video)
            control_layout.addWidget(self.video_slider, 1)
            
            control_layout.addStretch()
            
            # Exit button
            btn_exit = QPushButton("✕ Exit")
            btn_exit.setStyleSheet("""
                QPushButton {
                    background: rgba(255, 80, 80, 0.5);
                    border: 1px solid #FF5050;
                    border-radius: 4px;
                    padding: 6px 12px;
                    font-family: 'Segoe Print';
                    font-size: 14px;
                    color: #FFFFFF;
                    font-weight: 600;
                    min-width: 60px;
                }
                QPushButton:hover { background: rgba(255, 80, 80, 0.7); }
                QPushButton:pressed { background: rgba(255, 80, 80, 0.9); }
            """)
            btn_exit.clicked.connect(self._exit_elearning_video)
            control_layout.addWidget(btn_exit)
            
            player_layout.addWidget(control_bar)
            
            # Add to content area
            content_l = self.content.layout()
            content_l.insertWidget(2, self.elearning_video_player)
        
        self.elearning_video_player.setVisible(True)
        
        # Create media player if not exists
        if not hasattr(self, 'elearning_media_player'):
            self.elearning_media_player = QMediaPlayer()
            self.elearning_audio_output = QAudioOutput()
            self.elearning_media_player.setAudioOutput(self.elearning_audio_output)
            
            # Set video output if QVideoWidget is available
            if QVideoWidget is not None and isinstance(self.video_output, QVideoWidget):
                self.elearning_media_player.setVideoOutput(self.video_output)
            
            # Connect signals
            self.elearning_media_player.positionChanged.connect(self._update_video_position)
            self.elearning_media_player.durationChanged.connect(self._update_video_duration)
            self.elearning_media_player.playbackStateChanged.connect(self._on_playback_state_changed)
        
        # Set and play video
        self.elearning_media_player.setSource(QUrl.fromLocalFile(os.path.abspath(video_path)))
        self.elearning_media_player.play()
    
    def _toggle_video_playback(self):
        """Toggle video play/pause."""
        try:
            # Check if media player exists and has valid state
            if not hasattr(self, 'elearning_media_player'):
                return
            
            from PySide6.QtMultimedia import QMediaPlayer
            
            current_state = self.elearning_media_player.playbackState()
            
            # In PySide6, PlayingState is an enum
            if current_state == QMediaPlayer.PlayingState:
                self.elearning_media_player.pause()
                self.btn_play_pause.setText("▶ Play")
            else:
                self.elearning_media_player.play()
                self.btn_play_pause.setText("⏸ Pause")
        except Exception as e:
            # Fallback: just toggle play/pause
            try:
                if hasattr(self, 'elearning_media_player'):
                    if self.elearning_media_player.isPlaying():
                        self.elearning_media_player.pause()
                        self.btn_play_pause.setText("▶ Play")
                    else:
                        self.elearning_media_player.play()
                        self.btn_play_pause.setText("⏸ Pause")
            except Exception:
                pass
    
    def _seek_video(self, position):
        """Seek to video position."""
        if hasattr(self, 'elearning_media_player'):
            self.elearning_media_player.setPosition(position)
    
    def _update_video_position(self, position):
        """Update video position display and slider."""
        if hasattr(self, 'video_slider'):
            self.video_slider.blockSignals(True)
            self.video_slider.setValue(position)
            self.video_slider.blockSignals(False)
        
        if hasattr(self, 'lbl_time'):
            current_sec = position // 1000
            current_min = current_sec // 60
            current_sec = current_sec % 60
            
            if hasattr(self, 'elearning_media_player'):
                duration = self.elearning_media_player.duration()
                total_sec = duration // 1000
                total_min = total_sec // 60
                total_sec = total_sec % 60
                
                self.lbl_time.setText(f"{current_min:02d}:{current_sec:02d} / {total_min:02d}:{total_sec:02d}")
    
    def _update_video_duration(self, duration):
        """Update video duration for slider."""
        if hasattr(self, 'video_slider'):
            self.video_slider.setMaximum(duration)
    
    def _on_playback_state_changed(self):
        """Handle playback state change."""
        try:
            if hasattr(self, 'elearning_media_player') and hasattr(self, 'btn_play_pause'):
                from PySide6.QtMultimedia import QMediaPlayer
                
                current_state = self.elearning_media_player.playbackState()
                if current_state == QMediaPlayer.PlayingState:
                    self.btn_play_pause.setText("⏸ Pause")
                else:
                    self.btn_play_pause.setText("▶ Play")
        except Exception:
            pass
    
    def _cleanup_elearning_video(self):
        """Cleanup E-learning video player and hide all video-related widgets."""
        try:
            # Stop media player if it exists and is playing
            if hasattr(self, 'elearning_media_player'):
                self.elearning_media_player.stop()
        except Exception:
            pass
        
        # Hide video player if exists
        if hasattr(self, 'elearning_video_player'):
            try:
                self.elearning_video_player.setVisible(False)
            except Exception:
                pass
        
        # Hide container if exists
        if hasattr(self, 'elearning_container'):
            try:
                self.elearning_container.setVisible(False)
            except Exception:
                pass
        
        # Hide learning materials if exists
        if hasattr(self, 'learning_materials_container'):
            try:
                self.learning_materials_container.setVisible(False)
            except Exception:
                pass
    
    def _cleanup_practice_containers(self):
        """Cleanup practice-related containers and quiz module."""
        try:
            # Hide practice container
            if hasattr(self, 'practice_container'):
                self.practice_container.setVisible(False)
        except Exception:
            pass
        
        try:
            # Hide topic container
            if hasattr(self, 'topic_container'):
                self.topic_container.setVisible(False)
        except Exception:
            pass
        
        try:
            # Hide quiz module and stop audio
            if hasattr(self, 'quiz_module'):
                self.quiz_module.setVisible(False)
                # Stop audio playback
                if hasattr(self.quiz_module, 'audio_player'):
                    self.quiz_module.audio_player.stop()
        except Exception:
            pass
        
        try:
            # Hide completion frame
            if hasattr(self, '_completion_frame'):
                self._completion_frame.setVisible(False)
        except Exception:
            pass
    
    def _exit_elearning_video(self):
        """Exit video player and return to thumbnail view."""
        # Stop playback
        if hasattr(self, 'elearning_media_player'):
            self.elearning_media_player.stop()
        
        # Hide video player
        if hasattr(self, 'elearning_video_player'):
            self.elearning_video_player.setVisible(False)
        
        # Show thumbnail container
        if hasattr(self, 'elearning_container'):
            self.elearning_container.setVisible(True)

    def _show_practice_options(self):
        """Show practice mode selection buttons."""
        # 隐藏所有其他内容容器
        self._hide_all_content_containers()
        
        # Hide content view
        self.content_view.setVisible(False)
        
        # Hide topic container
        if hasattr(self, 'topic_container'):
            self.topic_container.setVisible(False)
        
        # Hide quiz module
        if hasattr(self, 'quiz_module'):
            self.quiz_module.setVisible(False)
        
        # Hide completion frame
        if hasattr(self, '_completion_frame'):
            self._completion_frame.setVisible(False)
        
        # Show and set title
        self.content_title.setText("Practice Questions")
        self.content_title.setVisible(True)
        
        # Create practice container if not exists
        if not hasattr(self, 'practice_container'):
            self.practice_container = QFrame()
            self.practice_container.setStyleSheet("background: transparent;")
            button_layout = QVBoxLayout(self.practice_container)
            button_layout.setSpacing(16)
            button_layout.setContentsMargins(0, 0, 0, 0)
            
            # Random Practice button
            btn_random = QPushButton("Random Practice\n(Random Selection)")
            btn_random.setStyleSheet("""
                QPushButton {
                    background: rgba(77, 163, 255, 0.2);
                    border: 2px solid #4DA3FF;
                    border-radius: 8px;
                    padding: 16px;
                    font-family: 'Segoe Print', 'Segoe UI', Arial;
                    font-size: 16px;
                    font-weight: 600;
                    color: #003366;
                    min-height: 80px;
                }
                QPushButton:hover {
                    background: rgba(77, 163, 255, 0.3);
                    border: 2px solid #234f8d;
                }
                QPushButton:pressed {
                    background: rgba(77, 163, 255, 0.4);
                }
            """)
            btn_random.clicked.connect(self._start_random_practice)
            button_layout.addWidget(btn_random)
            
            # Topic-Based Practice button
            btn_topic = QPushButton("Topic-Based Practice\n(Choose a topic)")
            btn_topic.setStyleSheet("""
                QPushButton {
                    background: rgba(77, 163, 255, 0.2);
                    border: 2px solid #4DA3FF;
                    border-radius: 8px;
                    padding: 16px;
                    font-family: 'Segoe Print', 'Segoe UI', Arial;
                    font-size: 16px;
                    font-weight: 600;
                    color: #003366;
                    min-height: 80px;
                }
                QPushButton:hover {
                    background: rgba(77, 163, 255, 0.3);
                    border: 2px solid #234f8d;
                }
                QPushButton:pressed {
                    background: rgba(77, 163, 255, 0.4);
                }
            """)
            btn_topic.clicked.connect(self._show_topic_options)
            button_layout.addWidget(btn_topic)
            
            button_layout.addStretch()
            
            # Add to content area
            content_l = self.content.layout()
            content_l.insertWidget(2, self.practice_container)
        
        self.practice_container.setVisible(True)
    
    def _start_random_practice(self):
        """Start random practice with all questions shuffled."""
        # Hide practice options
        if hasattr(self, 'practice_container'):
            self.practice_container.setVisible(False)
        
        # Hide topic container if visible
        if hasattr(self, 'topic_container'):
            self.topic_container.setVisible(False)
        
        # Create or show quiz module
        if not hasattr(self, 'quiz_module'):
            self.quiz_module = QuizModule()
            quiz_path = os.path.join("assets", "epidural_quiz_questions.json")
            self.quiz_module.load_quiz_data(quiz_path)
            
            # Connect completion signal
            self.quiz_module.quiz_completed.connect(self._on_quiz_completed)
            # Connect back button signal
            self.quiz_module.back_clicked.connect(self._on_quiz_back)
            
            # Add to content area
            content_l = self.content.layout()
            content_l.insertWidget(2, self.quiz_module)
        
        self.quiz_module.setVisible(True)
        
        # Get all question IDs and shuffle
        all_questions = list(self.quiz_module.questions.keys())
        random.shuffle(all_questions)
        
        # Start quiz
        self.quiz_module.start_quiz(all_questions)
    
    def _show_topic_options(self):
        """Show topic selection buttons."""
        # 隐藏所有其他内容容器
        self._hide_all_content_containers()
        
        # Hide practice options
        if hasattr(self, 'practice_container'):
            self.practice_container.setVisible(False)
        
        # Hide quiz module if visible
        if hasattr(self, 'quiz_module'):
            self.quiz_module.setVisible(False)
        
        # Hide completion frame if visible
        if hasattr(self, '_completion_frame'):
            self._completion_frame.setVisible(False)
        
        # Create topic container if not exists
        if not hasattr(self, 'topic_container'):
            self.topic_container = QFrame()
            self.topic_container.setStyleSheet("background: transparent;")
            button_layout = QVBoxLayout(self.topic_container)
            button_layout.setSpacing(16)
            button_layout.setContentsMargins(0, 0, 0, 0)
            
            # Topic 1 button (in order)
            btn_topic1 = QPushButton("Topic 1")
            btn_topic1.setStyleSheet("""
                QPushButton {
                    background: rgba(77, 163, 255, 0.2);
                    border: 2px solid #4DA3FF;
                    border-radius: 8px;
                    padding: 16px;
                    font-family: 'Segoe Print', 'Segoe UI', Arial;
                    font-size: 16px;
                    font-weight: 600;
                    color: #003366;
                    min-height: 80px;
                }
                QPushButton:hover {
                    background: rgba(77, 163, 255, 0.3);
                    border: 2px solid #234f8d;
                }
                QPushButton:pressed {
                    background: rgba(77, 163, 255, 0.4);
                }
            """)
            btn_topic1.clicked.connect(lambda: self._start_topic_practice("topic1"))
            button_layout.addWidget(btn_topic1)
            
            # Topic 2 button (reverse order)
            btn_topic2 = QPushButton("Topic 2")
            btn_topic2.setStyleSheet("""
                QPushButton {
                    background: rgba(77, 163, 255, 0.2);
                    border: 2px solid #4DA3FF;
                    border-radius: 8px;
                    padding: 16px;
                    font-family: 'Segoe Print', 'Segoe UI', Arial;
                    font-size: 16px;
                    font-weight: 600;
                    color: #003366;
                    min-height: 80px;
                }
                QPushButton:hover {
                    background: rgba(77, 163, 255, 0.3);
                    border: 2px solid #234f8d;
                }
                QPushButton:pressed {
                    background: rgba(77, 163, 255, 0.4);
                }
            """)
            btn_topic2.clicked.connect(lambda: self._start_topic_practice("topic2"))
            button_layout.addWidget(btn_topic2)
            
            # Back button
            btn_back = QPushButton("← Back to Practice Menu")
            btn_back.setStyleSheet("""
                QPushButton {
                    background: rgba(200, 200, 200, 0.3);
                    border: 2px solid #999999;
                    border-radius: 8px;
                    padding: 10px;
                    font-family: 'Segoe Print', 'Segoe UI', Arial;
                    font-size: 14px;
                    font-weight: 600;
                    color: #003366;
                }
                QPushButton:hover {
                    background: rgba(200, 200, 200, 0.4);
                }
                QPushButton:pressed {
                    background: rgba(200, 200, 200, 0.5);
                }
            """)
            btn_back.clicked.connect(self._show_practice_options)
            button_layout.addWidget(btn_back)
            
            button_layout.addStretch()
            
            # Add to content area
            content_l = self.content.layout()
            content_l.insertWidget(2, self.topic_container)
        
        self.topic_container.setVisible(True)
    
    def _start_topic_practice(self, topic_id):
        """Start topic-based practice."""
        # Hide topic container
        if hasattr(self, 'topic_container'):
            self.topic_container.setVisible(False)
        
        # Create or show quiz module
        if not hasattr(self, 'quiz_module'):
            self.quiz_module = QuizModule()
            quiz_path = os.path.join("assets", "epidural_quiz_questions.json")
            self.quiz_module.load_quiz_data(quiz_path)
            
            # Connect completion signal
            self.quiz_module.quiz_completed.connect(self._on_quiz_completed)
            # Connect back button signal
            self.quiz_module.back_clicked.connect(self._on_quiz_back)
            
            # Add to content area
            content_l = self.content.layout()
            content_l.insertWidget(2, self.quiz_module)
        
        self.quiz_module.setVisible(True)
        
        # Get all question IDs
        all_questions = list(self.quiz_module.questions.keys())
        
        if topic_id == "topic1":
            # Topic 1: Sequential order (Q1, Q2, Q3, Q4, Q5)
            question_list = sorted(all_questions)
        else:
            # Topic 2: Reverse order (Q5, Q4, Q3, Q2, Q1)
            question_list = sorted(all_questions, reverse=True)
        
        # Start quiz
        self.quiz_module.start_quiz(question_list)
    
    def _on_quiz_back(self):
        """Handle back button click in quiz."""
        # Hide quiz module
        if hasattr(self, 'quiz_module'):
            self.quiz_module.setVisible(False)
        
        # Show practice options
        self._show_practice_options()
    
    def _on_quiz_completed(self):
        """Handle quiz completion."""
        if not hasattr(self, 'quiz_module'):
            return
        
        # Check if in training mode
        if hasattr(self.quiz_module, 'training_mode') and self.quiz_module.training_mode:
            # Training mode: check if answered correctly
            correct, total = self.quiz_module.get_score()
            is_correct = (correct == total)  # 只有全部答对才算成功
            
            print(f"[Training] Quiz completed: {correct}/{total} correct, is_correct={is_correct}")
            self.quiz_module.setVisible(False)
            
            # 恢复Phase 4的拔针操作，并传递答题结果
            if hasattr(self, 'current_training') and self.current_training:
                # record the quiz result into the training module (so records can include accuracy)
                try:
                    qid = getattr(self, '_pending_training_quiz_id', None)
                    if qid:
                        try:
                            self.current_training.record_quiz_result(qid, is_correct)
                        except Exception as e:
                            print(f"[Training] Error recording quiz result: {e}")
                    # clear pending id
                    self._pending_training_quiz_id = None
                except Exception:
                    pass
                self.current_training.resume_phase4(quiz_correct=is_correct)
            
            return
        
        # Practice mode: show score and completion message
        # Get score
        correct, total = self.quiz_module.get_score()
        
        # Save to practice history
        self._save_practice_record(correct, total)
        
        # Hide quiz module
        self.quiz_module.setVisible(False)
        
        # Play pass.mp3
        pass_audio_path = os.path.join("assets", "pass.mp3")
        if os.path.exists(pass_audio_path):
            audio_player = QMediaPlayer()
            audio_output = QAudioOutput()
            audio_player.setAudioOutput(audio_output)
            audio_player.setSource(QUrl.fromLocalFile(os.path.abspath(pass_audio_path)))
            audio_player.play()
            
            # Store player to prevent garbage collection
            self._completion_audio_player = audio_player
        
        # Show completion message
        self._show_quiz_completion_message(correct, total)
    
    def _show_quiz_completion_message(self, correct, total):
        """Show quiz completion message."""
        # Play pass.mp3 when quiz completes
        pass_audio_path = os.path.join("assets", "pass.mp3")
        if os.path.exists(pass_audio_path):
            pass_player = QMediaPlayer()
            pass_output = QAudioOutput()
            pass_player.setAudioOutput(pass_output)
            pass_player.setSource(QUrl.fromLocalFile(os.path.abspath(pass_audio_path)))
            pass_player.play()
            # Store to prevent garbage collection
            self._pass_audio_player = pass_player
        
        # Create completion container
        completion_frame = QFrame()
        completion_frame.setStyleSheet("background: transparent;")
        completion_layout = QVBoxLayout(completion_frame)
        completion_layout.setSpacing(20)
        completion_layout.setContentsMargins(0, 0, 0, 0)
        
        # Completion message
        lbl_completion = QLabel(f"Quiz Completed!\n\nYour Score: {correct}/{total}")
        lbl_completion.setStyleSheet("""
            font-family: 'Segoe Print', 'Segoe UI', Arial;
            font-size: 28px;
            font-weight: 700;
            color: #003366;
            background: rgba(200, 255, 200, 0.3);
            padding: 20px;
            border-radius: 10px;
        """)
        lbl_completion.setAlignment(Qt.AlignCenter)
        completion_layout.addWidget(lbl_completion)
        
        # Back to practice menu button
        btn_back = QPushButton("← Back to Practice Menu")
        btn_back.setStyleSheet("""
            QPushButton {
                background: rgba(77, 163, 255, 0.3);
                border: 2px solid #4DA3FF;
                border-radius: 8px;
                padding: 12px;
                font-family: 'Segoe Print', 'Segoe UI', Arial;
                font-size: 16px;
                font-weight: 600;
                color: #003366;
                min-height: 50px;
            }
            QPushButton:hover {
                background: rgba(77, 163, 255, 0.4);
            }
            QPushButton:pressed {
                background: rgba(77, 163, 255, 0.5);
            }
        """)
        btn_back.clicked.connect(self._return_to_practice_options)
        completion_layout.addWidget(btn_back)
        
        completion_layout.addStretch()
        
        # Store the completion frame
        self._completion_frame = completion_frame
        
        # Add to content area and raise to front
        content_l = self.content.layout()
        content_l.insertWidget(2, completion_frame)
        completion_frame.setVisible(True)
        completion_frame.raise_()
    
    def _return_to_practice_options(self):
        """Return to practice menu."""
        # Hide completion frame
        if hasattr(self, '_completion_frame'):
            self._completion_frame.setVisible(False)
        
        # Hide topic container
        if hasattr(self, 'topic_container'):
            self.topic_container.setVisible(False)
        
        # Hide quiz module
        if hasattr(self, 'quiz_module'):
            self.quiz_module.setVisible(False)
        
        # Show practice options
        self._show_practice_options()

    def _show_practice_records(self):
        """Show practice records with statistics and curve."""
        self.content_view.setVisible(False)
        self.content_title.setText("Practice Records")
        self.content_title.setVisible(True)
        
        # Always recreate the container to ensure fresh display
        if hasattr(self, 'practice_records_container') and self.practice_records_container:
            try:
                self.content.layout().removeWidget(self.practice_records_container)
                self.practice_records_container.deleteLater()
            except:
                pass
        
        self.practice_records_container = QFrame()
        self.practice_records_container.setStyleSheet("background: transparent;")
        records_layout = QVBoxLayout(self.practice_records_container)
        records_layout.setSpacing(12)
        records_layout.setContentsMargins(0, 0, 0, 0)
        
        # Statistics panel
        stats_frame = QFrame()
        stats_frame.setStyleSheet("background: rgba(255, 255, 255, 0.3); border: 2px solid rgba(77, 163, 255, 0.3); border-radius: 8px; padding: 12px;")
        stats_layout = QHBoxLayout(stats_frame)
        stats_layout.setSpacing(20)
        
        # Overall accuracy label
        self.lbl_overall_accuracy = QLabel("Overall Accuracy: 0%")
        self.lbl_overall_accuracy.setStyleSheet("font-family: 'Segoe Print'; font-size: 16px; color: #003366; font-weight: 700;")
        stats_layout.addWidget(self.lbl_overall_accuracy)
        
        # Recent attempts label
        self.lbl_recent_accuracy = QLabel("Recent 10: 0%")
        self.lbl_recent_accuracy.setStyleSheet("font-family: 'Segoe Print'; font-size: 16px; color: #234f8d; font-weight: 600;")
        stats_layout.addWidget(self.lbl_recent_accuracy)
        
        # Info label
        lbl_info = QLabel("(Statistics based on first attempt only)")
        lbl_info.setStyleSheet("font-family: 'Segoe Print'; font-size: 12px; color: #666666; font-style: italic;")
        stats_layout.addWidget(lbl_info)
        
        stats_layout.addStretch()
        records_layout.addWidget(stats_frame)
        
        # Chart area - placeholder for matplotlib figure
        self.records_chart_container = QFrame()
        self.records_chart_container.setStyleSheet("background: rgba(255, 255, 255, 0.2); border: 2px solid rgba(77, 163, 255, 0.2); border-radius: 8px;")
        self.records_chart_layout = QVBoxLayout(self.records_chart_container)
        self.records_chart_layout.setContentsMargins(8, 8, 8, 8)
        self.records_chart_layout.setSpacing(8)
        
        lbl_chart = QLabel("Practice Accuracy Trend (Last 10 Attempts)")
        lbl_chart.setStyleSheet("font-family: 'Segoe Print'; font-size: 14px; color: #003366; font-weight: 600;")
        self.records_chart_layout.addWidget(lbl_chart)
        
        # Chart will be added here dynamically
        self.records_chart_canvas = None
        
        records_layout.addWidget(self.records_chart_container, 1)
        
        # Add to content area
        content_l = self.content.layout()
        content_l.insertWidget(2, self.practice_records_container)
        
        self.practice_records_container.setVisible(True)
        self._update_practice_statistics()

    def _update_practice_statistics(self):
        """Update practice statistics from history file."""
        try:
            history_path = os.path.join("assets", "practice_history.json")
            if not os.path.exists(history_path):
                return
            
            with open(history_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            records = data.get("records", [])
            if not records:
                return
            
            # Calculate overall accuracy
            total_correct = sum(r.get("correct", 0) for r in records)
            total_questions = sum(r.get("total", 5) for r in records)
            overall_accuracy = int(total_correct * 100 / total_questions) if total_questions > 0 else 0
            
            self.lbl_overall_accuracy.setText(f"Overall Accuracy: {overall_accuracy}%")
            
            # Recent 10 attempts
            recent_10 = records[-10:] if len(records) >= 10 else records
            recent_correct = sum(r.get("correct", 0) for r in recent_10)
            recent_total = sum(r.get("total", 5) for r in recent_10)
            recent_accuracy = int(recent_correct * 100 / recent_total) if recent_total > 0 else 0
            self.lbl_recent_accuracy.setText(f"Recent 10: {recent_accuracy}%")
            
            # Draw chart
            self._draw_practice_chart(recent_10)
            
        except Exception as e:
            print(f"Error updating practice statistics: {e}")

    def _draw_practice_chart(self, recent_records):
        """Draw practice accuracy trend chart using matplotlib."""
        try:
            from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
            from matplotlib.figure import Figure
            
            # Check if we have data
            if not recent_records:
                print("[MainWindow] No records to draw chart")
                return
            
            print(f"[MainWindow] Drawing chart with {len(recent_records)} records")
            
            # Clear previous canvas - only remove canvas widgets, not the title
            widget_to_remove = None
            for i in range(self.records_chart_layout.count()):
                widget = self.records_chart_layout.itemAt(i).widget()
                if widget and hasattr(widget, '__class__') and 'FigureCanvas' in str(widget.__class__):
                    widget_to_remove = widget
                    break
            
            if widget_to_remove:
                self.records_chart_layout.removeWidget(widget_to_remove)
                widget_to_remove.deleteLater()
            
            # Create figure with better size
            fig = Figure(figsize=(7, 2.8), dpi=100)
            fig.patch.set_alpha(0.0)
            ax = fig.add_subplot(111)
            
            # Prepare data
            attempts = list(range(1, len(recent_records) + 1))
            accuracies = [r.get("accuracy", 0) for r in recent_records]
            
            print(f"[MainWindow] Attempts: {attempts}, Accuracies: {accuracies}")
            
            # Plot - use matplotlib-compatible colors
            ax.plot(attempts, accuracies, marker='o', linestyle='-', linewidth=2.5, 
                   color='#4DA3FF', markersize=8, markerfacecolor='#4DA3FF', 
                   markeredgecolor='#003366', markeredgewidth=2)
            ax.fill_between(attempts, accuracies, alpha=0.25, color='#4DA3FF')
            
            # Styling - use hex colors and tuples instead of rgba()
            ax.set_xlabel("Attempt", fontsize=12, color='#003366', weight='bold')
            ax.set_ylabel("Accuracy (%)", fontsize=12, color='#003366', weight='bold')
            ax.set_ylim(0, 105)
            ax.set_xlim(0.5, len(recent_records) + 0.5)
            ax.grid(True, alpha=0.3, linestyle='--', color='#CCCCCC')
            ax.set_facecolor((1.0, 1.0, 1.0, 0.05))  # Use tuple instead of rgba()
            
            # Set tick colors and labels
            ax.tick_params(colors='#003366', labelsize=10)
            ax.set_xticks(attempts)
            
            # Spine styling
            for spine in ax.spines.values():
                spine.set_color('#4DA3FF')
                spine.set_linewidth(2)
            
            fig.tight_layout(pad=1.0)
            
            # Create and add canvas
            canvas = FigureCanvas(fig)
            self.records_chart_layout.addWidget(canvas, 1)
            
            # Force layout update
            self.records_chart_container.update()
            
            print(f"[MainWindow] Chart successfully drawn")
            
        except ImportError as e:
            print(f"[MainWindow] matplotlib not available: {e}")
            self._show_simple_chart(recent_records)
        except Exception as e:
            print(f"[MainWindow] Error drawing practice chart: {e}")
            import traceback
            traceback.print_exc()
            # Fall back to simple chart
            self._show_simple_chart(recent_records)

    def _show_simple_chart(self, recent_records):
        """Show a simple text-based chart alternative when matplotlib is not available."""
        try:
            # Remove any existing canvas
            for i in range(self.records_chart_layout.count()):
                widget = self.records_chart_layout.itemAt(i).widget()
                if widget and hasattr(widget, '__class__') and 'FigureCanvas' in str(widget.__class__):
                    self.records_chart_layout.removeWidget(widget)
                    widget.deleteLater()
                    break
            
            # Create a text-based representation
            chart_text = "Accuracy Trend:\n\n"
            for i, record in enumerate(recent_records, 1):
                accuracy = record.get("accuracy", 0)
                bars = int(accuracy / 5)
                chart_text += f"Attempt {i:2d}: {'█' * bars}{'░' * (20 - bars)} {accuracy}%\n"
            
            text_widget = QTextEdit()
            text_widget.setReadOnly(True)
            text_widget.setText(chart_text)
            text_widget.setStyleSheet("""
                QTextEdit {
                    font-family: 'Courier New', monospace;
                    font-size: 11px;
                    color: #003366;
                    background: rgba(255, 255, 255, 0.05);
                    border: none;
                    padding: 8px;
                }
            """)
            text_widget.setMaximumHeight(180)
            
            self.records_chart_layout.addWidget(text_widget, 1)
            print("[MainWindow] Simple chart displayed")
            
        except Exception as e:
            print(f"[MainWindow] Error showing simple chart: {e}")

    def _cleanup_practice_records(self):
        """Cleanup practice records container."""
        try:
            if hasattr(self, 'practice_records_container'):
                self.practice_records_container.setVisible(False)
        except Exception:
            pass

    def _show_training_records(self):
        """Show training (simulation) records with statistics."""
        self.content_view.setVisible(False)
        self.content_title.setText("Training Records")
        self.content_title.setVisible(True)
        
        # Always recreate the container to ensure fresh display
        if hasattr(self, 'training_records_container') and self.training_records_container:
            try:
                self.content.layout().removeWidget(self.training_records_container)
                self.training_records_container.deleteLater()
            except:
                pass
        
        self.training_records_container = QFrame()
        self.training_records_container.setStyleSheet("background: transparent;")
        records_layout = QVBoxLayout(self.training_records_container)
        records_layout.setSpacing(12)
        records_layout.setContentsMargins(0, 0, 0, 0)
        
        # Statistics panel
        stats_frame = QFrame()
        stats_frame.setStyleSheet("background: rgba(255, 255, 255, 0.3); border: 2px solid rgba(77, 163, 255, 0.3); border-radius: 8px; padding: 12px;")
        stats_layout = QHBoxLayout(stats_frame)
        stats_layout.setSpacing(20)
        
        # Training count
        self.lbl_training_count = QLabel("Total Trainings: 0")
        self.lbl_training_count.setStyleSheet("font-family: 'Segoe Print'; font-size: 16px; color: #003366; font-weight: 700;")
        stats_layout.addWidget(self.lbl_training_count)
        
        # Total time
        self.lbl_training_time = QLabel("Total Time: 0s")
        self.lbl_training_time.setStyleSheet("font-family: 'Segoe Print'; font-size: 16px; color: #234f8d; font-weight: 600;")
        stats_layout.addWidget(self.lbl_training_time)
        
        # Average time
        self.lbl_training_avg = QLabel("Average Time: 0s")
        self.lbl_training_avg.setStyleSheet("font-family: 'Segoe Print'; font-size: 16px; color: #234f8d; font-weight: 600;")
        stats_layout.addWidget(self.lbl_training_avg)
        
        stats_layout.addStretch()
        records_layout.addWidget(stats_frame)
        
        # Records list
        self.training_records_list = QListWidget()
        self.training_records_list.setStyleSheet("""
            QListWidget {
                background: rgba(255, 255, 255, 0.2);
                border: 2px solid rgba(77, 163, 255, 0.2);
                border-radius: 8px;
                outline: 0;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid rgba(77, 163, 255, 0.1);
                color: #003366;
                background: transparent;
            }
            QListWidget::item:hover {
                background: rgba(77, 163, 255, 0.1);
            }
            QListWidget::item:selected {
                background: rgba(77, 163, 255, 0.2);
                color: #003366;
            }
        """)
        self.training_records_list.setFont(QFont('Segoe Print', 11))
        records_layout.addWidget(self.training_records_list, 1)
        
        # 添加两个图表容器（时间和正确率趋势）
        charts_layout = QHBoxLayout()
        charts_layout.setSpacing(12)
        
        # 时间趋势图容器
        time_chart_container = QFrame()
        time_chart_container.setStyleSheet("background: transparent;")
        time_chart_layout = QVBoxLayout(time_chart_container)
        time_chart_layout.setContentsMargins(0, 0, 0, 0)
        time_chart_title = QLabel("Training Time Trend")
        time_chart_title.setFont(QFont('Segoe Print', 12, QFont.Bold))
        time_chart_title.setStyleSheet("color: #003366;")
        time_chart_layout.addWidget(time_chart_title)
        self.training_time_chart_layout = QVBoxLayout()
        self.training_time_chart_layout.setContentsMargins(0, 0, 0, 0)
        time_chart_layout.addLayout(self.training_time_chart_layout)
        charts_layout.addWidget(time_chart_container)
        
        # 正确率趋势图容器
        accuracy_chart_container = QFrame()
        accuracy_chart_container.setStyleSheet("background: transparent;")
        accuracy_chart_layout = QVBoxLayout(accuracy_chart_container)
        accuracy_chart_layout.setContentsMargins(0, 0, 0, 0)
        accuracy_chart_title = QLabel("Accuracy Trend")
        accuracy_chart_title.setFont(QFont('Segoe Print', 12, QFont.Bold))
        accuracy_chart_title.setStyleSheet("color: #003366;")
        accuracy_chart_layout.addWidget(accuracy_chart_title)
        self.training_accuracy_chart_layout = QVBoxLayout()
        self.training_accuracy_chart_layout.setContentsMargins(0, 0, 0, 0)
        accuracy_chart_layout.addLayout(self.training_accuracy_chart_layout)
        charts_layout.addWidget(accuracy_chart_container)
        
        records_layout.addLayout(charts_layout, 1)
        
        # Add to content area
        content_l = self.content.layout()
        content_l.insertWidget(2, self.training_records_container)
        
        self.training_records_container.setVisible(True)
        self._update_training_records()

    def _update_training_records(self):
        """Update training records from storage with charts."""
        try:
            from app.training_records import get_training_record_manager
            
            manager = get_training_record_manager()
            stats = manager.get_training_statistics(self.user.username)
            
            # Update statistics
            self.lbl_training_count.setText(f"Total Trainings: {stats['total_trainings']}")
            total_minutes = int(stats['total_time'] // 60)
            self.lbl_training_time.setText(f"Total Time: {total_minutes}m {int(stats['total_time'] % 60)}s")
            avg_seconds = int(stats['avg_time'])
            self.lbl_training_avg.setText(f"Average Time: {avg_seconds}s")
            
            # Collect records data
            details = stats['details']
            elapsed_times = []
            accuracies = []
            training_types = []
            
            for record in details:
                training_data = record.get('training_data', {})
                elapsed_time = training_data.get('elapsed_time', 0)
                accuracy = training_data.get('accuracy', 0)
                training_type = training_data.get('training_type', 'unknown')
                elapsed_times.append(elapsed_time)
                accuracies.append(accuracy)
                training_types.append(training_type)
            
            # Update records list
            self.training_records_list.clear()
            for i, record in enumerate(details):
                training_data = record.get('training_data', {})
                elapsed_time = training_data.get('elapsed_time', 0)
                accuracy = training_data.get('accuracy', 0)
                training_type = training_data.get('training_type', 'unknown')
                completed_at = record.get('completed_at', 'Unknown')
                
                # Format datetime
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(completed_at)
                    time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
                except:
                    time_str = completed_at[:10]
                
                # Create list item with training type and accuracy
                item_text = f"{time_str} | {training_type} | {elapsed_time:.1f}s | {accuracy:.0f}%"
                item = QListWidgetItem(item_text)
                self.training_records_list.addItem(item)
            
            # Draw charts
            if elapsed_times:
                self._draw_training_time_chart(elapsed_times)
                self._draw_training_accuracy_chart(accuracies)
            
        except Exception as e:
            print(f"Error updating training records: {e}")
            import traceback
            traceback.print_exc()
    
    def _draw_training_time_chart(self, elapsed_times):
        """Draw training time trend chart."""
        try:
            from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
            from matplotlib.figure import Figure
            
            # Clear previous canvas
            while self.training_time_chart_layout.count():
                widget = self.training_time_chart_layout.takeAt(0).widget()
                if widget and hasattr(widget, '__class__') and 'FigureCanvas' in str(widget.__class__):
                    widget.deleteLater()
            
            # Create figure
            fig = Figure(figsize=(5, 2.5), dpi=100)
            fig.patch.set_alpha(0.0)
            ax = fig.add_subplot(111)
            
            # Prepare data
            attempts = list(range(1, len(elapsed_times) + 1))
            
            # Plot
            ax.plot(attempts, elapsed_times, marker='o', linestyle='-', linewidth=2.5,
                   color='#4DA3FF', markersize=8, markerfacecolor='#4DA3FF',
                   markeredgecolor='#003366', markeredgewidth=2)
            ax.fill_between(attempts, elapsed_times, alpha=0.25, color='#4DA3FF')
            
            # Styling
            ax.set_xlabel("Attempt", fontsize=11, color='#003366', weight='bold')
            ax.set_ylabel("Time (seconds)", fontsize=11, color='#003366', weight='bold')
            ax.set_xlim(0.5, len(elapsed_times) + 0.5)
            ax.grid(True, alpha=0.3, linestyle='--', color='#CCCCCC')
            ax.set_facecolor((1.0, 1.0, 1.0, 0.05))
            
            # Styling ticks
            ax.tick_params(colors='#003366', labelsize=9)
            ax.set_xticks(attempts)
            
            # Spine styling
            for spine in ax.spines.values():
                spine.set_color('#4DA3FF')
                spine.set_linewidth(1.5)
            
            fig.tight_layout(pad=1.0)
            
            # Create and add canvas
            canvas = FigureCanvas(fig)
            self.training_time_chart_layout.addWidget(canvas)
            
        except Exception as e:
            print(f"Error drawing training time chart: {e}")
    
    def _draw_training_accuracy_chart(self, accuracies):
        """Draw training accuracy trend chart."""
        try:
            from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
            from matplotlib.figure import Figure
            
            # Clear previous canvas
            while self.training_accuracy_chart_layout.count():
                widget = self.training_accuracy_chart_layout.takeAt(0).widget()
                if widget and hasattr(widget, '__class__') and 'FigureCanvas' in str(widget.__class__):
                    widget.deleteLater()
            
            # Create figure
            fig = Figure(figsize=(5, 2.5), dpi=100)
            fig.patch.set_alpha(0.0)
            ax = fig.add_subplot(111)
            
            # Prepare data
            attempts = list(range(1, len(accuracies) + 1))
            
            # Plot
            ax.plot(attempts, accuracies, marker='o', linestyle='-', linewidth=2.5,
                   color='#00AA00', markersize=8, markerfacecolor='#00AA00',
                   markeredgecolor='#006600', markeredgewidth=2)
            ax.fill_between(attempts, accuracies, alpha=0.25, color='#00AA00')
            
            # Styling
            ax.set_xlabel("Attempt", fontsize=11, color='#003366', weight='bold')
            ax.set_ylabel("Accuracy (%)", fontsize=11, color='#003366', weight='bold')
            ax.set_ylim(0, 105)
            ax.set_xlim(0.5, len(accuracies) + 0.5)
            ax.grid(True, alpha=0.3, linestyle='--', color='#CCCCCC')
            ax.set_facecolor((1.0, 1.0, 1.0, 0.05))
            
            # Styling ticks
            ax.tick_params(colors='#003366', labelsize=9)
            ax.set_xticks(attempts)
            
            # Spine styling
            for spine in ax.spines.values():
                spine.set_color('#00AA00')
                spine.set_linewidth(1.5)
            
            fig.tight_layout(pad=1.0)
            
            # Create and add canvas
            canvas = FigureCanvas(fig)
            self.training_accuracy_chart_layout.addWidget(canvas)
            
        except Exception as e:
            print(f"Error drawing training accuracy chart: {e}")

    def _cleanup_training_records(self):
        """Cleanup training records container."""
        try:
            if hasattr(self, 'training_records_container'):
                self.training_records_container.setVisible(False)
        except Exception:
            pass
    
    def _init_ai_mentor(self):
        """初始化AI Nursing Mentor"""
        # 保证属性存在，避免后续访问时报错
        self.ai_mentor = None
        try:
            from app.ai_mentor import AIMentor

            # 尝试导入配置
            try:
                from app.ai_config_local import API_URL, API_KEY, MODEL, BASE_URL
            except ImportError:
                # 使用示例配置
                from app.ai_config_example import API_URL, API_KEY, MODEL, BASE_URL
                print("[MainWindow] Warning: Using example config. Please create ai_config_local.py with your API key")
                # 保持 self.ai_mentor 为 None
                return None

            # 验证API配置
            if API_KEY == "your-api-key-here" or not API_KEY:
                print("[MainWindow] Error: API key not configured. Please set it in app/ai_config_local.py")
                return None

            # 创建AI导师实例（支持传入 model/base_url）
            try:
                self.ai_mentor = AIMentor(API_URL, API_KEY, model=MODEL, base_url=BASE_URL)
            except Exception:
                # 兼容旧构造（若MODEL/BASE_URL不存在）
                self.ai_mentor = AIMentor(API_URL, API_KEY)

            print("[MainWindow] AI Mentor initialized successfully")
            return self.ai_mentor

        except ImportError as e:
            print(f"[MainWindow] Error importing AI Mentor: {e}")
            self.ai_mentor = None
            return None
        except Exception as e:
            print(f"[MainWindow] Error initializing AI Mentor: {e}")
            self.ai_mentor = None
            return None

    def _show_ai_mentor(self):
        """显示AI Nursing Mentor对话界面"""
        try:
            from app.ui.ai_mentor_widget import AIMentorWidget
            
            # 初始化AI Mentor（如果还没初始化）
            if not hasattr(self, 'ai_mentor') or self.ai_mentor is None:
                self._init_ai_mentor()
            # 如果初始化后仍然没有 ai_mentor，给出用户提示并返回
            if not hasattr(self, 'ai_mentor') or self.ai_mentor is None:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.warning(
                    self,
                    "AI Mentor Not Configured",
                    "AI Mentor is not configured.\n\nPlease create app/ai_config_local.py from app/ai_config_example.py and fill in your API key."
                )
                return
            
            # 创建或获取AI Mentor Widget
            if not hasattr(self, 'ai_mentor_widget') or self.ai_mentor_widget is None:
                self.ai_mentor_widget = AIMentorWidget(self.ai_mentor, self.content)
                content_l = self.content.layout()
                content_l.insertWidget(2, self.ai_mentor_widget)
            
            # 隐藏所有其他容器
            self._hide_all_content_containers()
            
            # 显示AI Mentor
            self.ai_mentor_widget.setVisible(True)
            self.content_title.setText("AI Nursing Mentor")
            self.content_title.setVisible(True)
            
        except Exception as e:
            print(f"Error showing AI Mentor: {e}")
            import traceback
            traceback.print_exc()
            
            # 显示错误信息
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(
                self,
                "Error",
                "Failed to load AI Mentor.\n\n"
                "Please ensure:\n"
                "1. Create app/ai_config_local.py with your API key\n"
                "2. Copy from app/ai_config_example.py\n"
                "3. Fill in your actual API key"
            )

    def _save_practice_record(self, correct, total):
        """Save a practice record to history file."""
        try:
            from datetime import datetime
            
            history_path = os.path.join("assets", "practice_history.json")
            
            # Load existing data or create new
            if os.path.exists(history_path):
                with open(history_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            else:
                data = {"records": []}
            
            # Calculate accuracy percentage
            accuracy = int(correct * 100 / total) if total > 0 else 0
            
            # Create new record
            record = {
                "date": datetime.now().strftime("%Y-%m-%d"),
                "accuracy": accuracy,
                "correct": correct,
                "total": total
            }
            
            # Add to records
            data["records"].append(record)
            
            # Save back to file
            with open(history_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            print(f"[MainWindow] Saved practice record: {accuracy}% ({correct}/{total})")
            
        except Exception as e:
            print(f"Error saving practice record: {e}")

    def _show_simulation_options(self):
        """Show three training option buttons in simulation page."""
        # 隐藏所有其他内容容器
        self._hide_all_content_containers()
        
        # Hide welcome quote and content view
        self.welcome_quote.setVisible(False)
        self.content_view.setVisible(False)
        
        # Show and set title
        self.content_title.setText("Simulation Training")
        self.content_title.setVisible(True)
        
        # Create container for the three buttons
        if not hasattr(self, 'simulation_container'):
            self.simulation_container = QFrame()
            self.simulation_container.setStyleSheet("background: transparent;")
            button_layout = QHBoxLayout(self.simulation_container)
            button_layout.setSpacing(12)
            button_layout.setContentsMargins(0, 0, 0, 0)
            
            # Four training options: Removal split into simulator/no-simulator modes
            options = [
                ("Comprehensive\nTraining", "comprehensive"),
                ("Change dressing of\nepidural catheter\ninsertion site", "change_dressing"),
                ("Removal of\nepidural catheter\n(Simulator)", "remove_needle_simulator"),
                ("Removal of\nepidural catheter\n(No Simulator)", "remove_needle_no_simulator")
            ]
            
            for option_text, option_key in options:
                btn = QPushButton(option_text)
                btn.setStyleSheet("""
                    QPushButton {
                        background: rgba(77, 163, 255, 0.2);
                        border: 2px solid #4DA3FF;
                        border-radius: 8px;
                        padding: 16px;
                        font-family: 'Segoe Print', 'Segoe UI', Arial;
                        font-size: 16px;
                        font-weight: 600;
                        color: #003366;
                        min-height: 100px;
                    }
                    QPushButton:hover {
                        background: rgba(77, 163, 255, 0.3);
                        border: 2px solid #234f8d;
                    }
                    QPushButton:pressed {
                        background: rgba(77, 163, 255, 0.4);
                    }
                """)
                btn.clicked.connect(lambda checked, key=option_key: self._on_training_button_click(key))
                button_layout.addWidget(btn)
            
            # Add to content area
            content_l = self.content.layout()
            # Insert after title (at position 2 after title, stretch, content_view)
            content_l.insertWidget(2, self.simulation_container)
        
        self.simulation_container.setVisible(True)
    def _hide_all_content_containers(self):
        """隐藏所有内容容器（Settings, Simulation, Practice, E-learning等）"""
        if hasattr(self, 'settings_container'):
            self.settings_container.setVisible(False)
        if hasattr(self, 'simulation_container'):
            self.simulation_container.setVisible(False)
        if hasattr(self, 'topic_container'):
            self.topic_container.setVisible(False)
        if hasattr(self, 'simulator_conn_widget'):
            self.simulator_conn_widget.setVisible(False)
        if hasattr(self, 'training_records_container'):
            self.training_records_container.setVisible(False)
        if hasattr(self, 'ai_mentor_widget') and self.ai_mentor_widget:
            try:
                # hide and clear messages when switching menus
                self.ai_mentor_widget.setVisible(False)
                if hasattr(self.ai_mentor_widget, 'clear_messages'):
                    self.ai_mentor_widget.clear_messages()
            except Exception:
                pass
        # Also hide the generic content view and title so they don't bleed through
        try:
            if hasattr(self, 'content_view') and self.content_view:
                self.content_view.setVisible(False)
        except Exception:
            pass
        try:
            if hasattr(self, 'content_title') and self.content_title:
                self.content_title.setVisible(False)
        except Exception:
            pass
        try:
            if hasattr(self, 'welcome_quote') and self.welcome_quote:
                self.welcome_quote.setVisible(False)
        except Exception:
            pass
    
    def _show_settings(self):
        """Show Settings page with both camera and font configuration"""
        # 隐藏所有其他内容容器
        self._hide_all_content_containers()
        
        # 停止任何正在进行的训练
        self._stop_current_training()
        
        # 清理E-learning视频播放器
        self._cleanup_elearning_video()
        
        # 清理Practice相关容器
        self._cleanup_practice_containers()
        
        # 清除菜单栏选中
        self.menu_list.clearSelection()
        
        # Hide other content
        self.welcome_quote.setVisible(False)
        if hasattr(self, 'simulation_container'):
            self.simulation_container.setVisible(False)
        if hasattr(self, 'simulator_conn_widget'):
            self.simulator_conn_widget.setVisible(False)
        
        # Show title
        self.content_title.setText("Settings")
        self.content_title.setVisible(True)
        self.content_view.setVisible(False)
        
        # 创建settings容器（包含摄像头和字体设置）
        if not hasattr(self, 'settings_container'):
            self.settings_container = QFrame()
            self.settings_container.setStyleSheet("background: white; border-radius: 8px;")
            settings_layout = QVBoxLayout(self.settings_container)
            settings_layout.setSpacing(20)
            settings_layout.setContentsMargins(20, 20, 20, 20)
            
            # 创建标签页容器（简单的手动标签页）
            tabs_frame = QFrame()
            tabs_layout = QHBoxLayout(tabs_frame)
            tabs_layout.setContentsMargins(0, 0, 0, 0)
            
            # 摄像头标签按钮
            self.btn_camera_tab = QPushButton("Camera Settings")
            self.btn_camera_tab.setMinimumWidth(150)
            self.btn_camera_tab.setMinimumHeight(40)
            self.btn_camera_tab.setStyleSheet("""
                QPushButton {
                    background: #4DA3FF;
                    color: white;
                    border: none;
                    border-radius: 5px;
                    font-weight: bold;
                    font-size: 12px;
                }
                QPushButton:hover { background: #3a7bc8; }
            """)
            self.btn_camera_tab.clicked.connect(self._show_camera_settings_tab)
            
            # 字体标签按钮
            self.btn_font_tab = QPushButton("Font Settings")
            self.btn_font_tab.setMinimumWidth(150)
            self.btn_font_tab.setMinimumHeight(40)
            self.btn_font_tab.setStyleSheet("""
                QPushButton {
                    background: #E0E0E0;
                    color: #333;
                    border: none;
                    border-radius: 5px;
                    font-weight: bold;
                    font-size: 12px;
                }
                QPushButton:hover { background: #D0D0D0; }
            """)
            self.btn_font_tab.clicked.connect(self._show_font_settings_tab)
            
            tabs_layout.addWidget(self.btn_camera_tab)
            tabs_layout.addWidget(self.btn_font_tab)
            tabs_layout.addStretch()
            settings_layout.addWidget(tabs_frame)
            
            # 内容切换区域
            self.settings_content = QFrame()
            self.settings_content.setStyleSheet("background: transparent;")
            self.settings_content_layout = QVBoxLayout(self.settings_content)
            self.settings_content_layout.setContentsMargins(0, 0, 0, 0)
            settings_layout.addWidget(self.settings_content)
            
            content_l = self.content.layout()
            content_l.insertWidget(2, self.settings_container)
        
        self.settings_container.setVisible(True)
        
        # 默认显示摄像头设置
        self._show_camera_settings_tab()
    
    def _show_camera_settings_tab(self):
        """显示摄像头设置标签"""
        # 隐藏字体settings widget
        if hasattr(self, 'settings_widget'):
            self.settings_widget.setVisible(False)
        
        # 清除之前的内容
        while self.settings_content_layout.count():
            widget = self.settings_content_layout.takeAt(0).widget()
            if widget:
                widget.setParent(None)
        
        # 更新标签按钮样式
        self.btn_camera_tab.setStyleSheet("""
            QPushButton {
                background: #4DA3FF;
                color: white;
                border: none;
                border-radius: 5px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover { background: #3a7bc8; }
        """)
        
        self.btn_font_tab.setStyleSheet("""
            QPushButton {
                background: #E0E0E0;
                color: #333;
                border: none;
                border-radius: 5px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover { background: #D0D0D0; }
        """)
        
        # 创建或获取摄像头管理器
        if not hasattr(self, 'camera_manager_widget'):
            self.camera_manager_widget = CameraManager()
        
        self.settings_content_layout.addWidget(self.camera_manager_widget)
        self.camera_manager_widget.setVisible(True)
    
    def _show_font_settings_tab(self):
        """显示字体设置标签"""
        # 隐藏摄像头settings widget
        if hasattr(self, 'camera_manager_widget'):
            self.camera_manager_widget.setVisible(False)
        
        # 清除之前的内容
        while self.settings_content_layout.count():
            widget = self.settings_content_layout.takeAt(0).widget()
            if widget:
                widget.setParent(None)
        
        # 更新标签按钮样式
        self.btn_camera_tab.setStyleSheet("""
            QPushButton {
                background: #E0E0E0;
                color: #333;
                border: none;
                border-radius: 5px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover { background: #D0D0D0; }
        """)
        
        self.btn_font_tab.setStyleSheet("""
            QPushButton {
                background: #4DA3FF;
                color: white;
                border: none;
                border-radius: 5px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover { background: #3a7bc8; }
        """)
        
        # 创建或获取字体设置widget
        if not hasattr(self, 'settings_widget'):
            self.settings_widget = SettingsWidget()
            self.settings_widget.font_changed.connect(self._apply_font_globally)
        
        self.settings_content_layout.addWidget(self.settings_widget)
        self.settings_widget.setVisible(True)
    
    def _apply_font_globally(self, font_name):
        """Apply selected font to all UI elements"""
        print(f"[Settings] Applying font: {font_name}")
        
        # Save font setting to user_settings.json
        try:
            settings = {"font": font_name}
            settings_path = os.path.join(os.path.dirname(__file__), "..", "..", "user_settings.json")
            os.makedirs(os.path.dirname(settings_path), exist_ok=True)
            with open(settings_path, 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=4, ensure_ascii=False)
            print(f"[Settings] Saved font to {settings_path}")
        except Exception as e:
            print(f"[Settings] Error saving font: {e}")
        
        # Apply font to main window and all children
        font = QFont(font_name, 11)
        self.setFont(font)
        
        # Apply to specific elements with custom sizes
        self._apply_font_recursive(self, font_name)
        
        print(f"[Settings] Font applied successfully to all UI")
    
    def _apply_font_recursive(self, widget, font_name):
        """Recursively apply font to widget and all children"""
        # Get current font size for this widget
        current_font = widget.font()
        size = current_font.pointSize() if current_font.pointSize() > 0 else 11
        weight = current_font.weight()
        
        # Apply new font with same size and weight
        new_font = QFont(font_name, size)
        new_font.setWeight(weight)
        widget.setFont(new_font)
        
        # Recursively apply to children
        for child in widget.findChildren(QWidget):
            current_font = child.font()
            size = current_font.pointSize() if current_font.pointSize() > 0 else 11
            weight = current_font.weight()
            
            new_font = QFont(font_name, size)
            new_font.setWeight(weight)
            child.setFont(new_font)
    
    def _show_simulator_connection(self):
        """Show Simulator Connection debug page"""
        # 隐藏所有其他内容容器
        self._hide_all_content_containers()
        
        # 停止任何正在进行的训练
        self._stop_current_training()
        
        # 清理E-learning视频播放器
        self._cleanup_elearning_video()
        
        # 清理Practice相关容器
        self._cleanup_practice_containers()
        
        # 清除菜单栏选中
        self.menu_list.clearSelection()
        
        # Hide other content
        self.welcome_quote.setVisible(False)
        
        # Show title
        self.content_title.setText("Simulator")
        self.content_title.setVisible(True)
        self.content_view.setVisible(False)
        
        # Create simulator connection widget if not exists
        if not hasattr(self, 'simulator_conn_widget'):
            self.simulator_conn_widget = QFrame()
            self.simulator_conn_widget.setStyleSheet("background: transparent;")
            conn_l = QVBoxLayout(self.simulator_conn_widget)
            conn_l.setSpacing(12)
            conn_l.setContentsMargins(0, 0, 0, 0)
            
            # WiFi Section
            wifi_frame = QFrame()
            wifi_frame.setStyleSheet("background: transparent;")
            wifi_l = QHBoxLayout(wifi_frame)
            
            wifi_label = QLabel("Current WiFi:")
            wifi_label.setStyleSheet("font-family: 'Segoe Print'; font-size: 16px; color: #003366; font-weight: 700;")
            wifi_l.addWidget(wifi_label)
            
            self.lbl_current_wifi = QLabel("Checking...")
            self.lbl_current_wifi.setStyleSheet("font-family: 'Segoe Print'; font-size: 16px; color: #234f8d; font-weight: 600;")
            self.lbl_current_wifi.setMinimumWidth(250)
            wifi_l.addWidget(self.lbl_current_wifi)
            
            btn_refresh = QPushButton("Refresh")
            btn_refresh.setStyleSheet("""
                QPushButton {
                    background: rgba(77, 163, 255, 0.3);
                    border: 2px solid #4DA3FF;
                    border-radius: 6px;
                    padding: 8px 16px;
                    font-family: 'Segoe Print';
                    font-size: 14px;
                    font-weight: 600;
                    color: #003366;
                    min-width: 100px;
                }
                QPushButton:hover { background: rgba(77, 163, 255, 0.4); }
                QPushButton:pressed { background: rgba(77, 163, 255, 0.5); }
            """)
            btn_refresh.clicked.connect(self._refresh_wifi_display)
            wifi_l.addWidget(btn_refresh)
            wifi_l.addStretch()
            conn_l.addWidget(wifi_frame)
            
            # Connection test section
            conn_test_frame = QFrame()
            conn_test_frame.setStyleSheet("background: transparent;")
            conn_test_l = QHBoxLayout(conn_test_frame)
            
            btn_connect = QPushButton("Test Connection")
            btn_connect.setStyleSheet("""
                QPushButton {
                    background: rgba(77, 163, 255, 0.3);
                    border: 2px solid #4DA3FF;
                    border-radius: 6px;
                    padding: 10px 20px;
                    font-family: 'Segoe Print';
                    font-size: 16px;
                    font-weight: 700;
                    color: #003366;
                    min-width: 150px;
                }
                QPushButton:hover { background: rgba(77, 163, 255, 0.4); }
                QPushButton:pressed { background: rgba(77, 163, 255, 0.5); }
            """)
            btn_connect.clicked.connect(self._test_hardware_connection)
            conn_test_l.addWidget(btn_connect)
            conn_test_l.addStretch()
            conn_l.addWidget(conn_test_frame)
            
            # Status display
            self.lbl_connection_status = QLabel("")
            self.lbl_connection_status.setStyleSheet("font-family: 'Segoe Print'; font-size: 16px; color: #003366; font-weight: 600;")
            self.lbl_connection_status.setWordWrap(True)
            self.lbl_connection_status.setMinimumHeight(60)
            conn_l.addWidget(self.lbl_connection_status)
            
            conn_l.addStretch()
            
            content_l = self.content.layout()
            content_l.insertWidget(2, self.simulator_conn_widget)
        
        # Refresh WiFi on display
        self._refresh_wifi_display()
        self.simulator_conn_widget.setVisible(True)
    
    def _refresh_wifi_display(self):
        """Refresh WiFi display in background thread"""
        try:
            from app.hardware_connector import WiFiThread
            
            # Prevent multiple concurrent WiFi checks
            if hasattr(self, 'wifi_thread') and self.wifi_thread and self.wifi_thread.isRunning():
                return  # Already checking, ignore new request
            
            # Create and start WiFi thread
            self.wifi_thread = WiFiThread()
            self.wifi_thread.wifi_ready.connect(self._on_wifi_ready)
            self.wifi_thread.finished.connect(lambda: self._cleanup_wifi_thread())
            self.wifi_thread.start()
            
            # Show waiting status
            self.lbl_current_wifi.setText("Checking...")
        except Exception as e:
            self.lbl_current_wifi.setText(f"Error")
    
    def _cleanup_wifi_thread(self):
        """Clean up WiFi thread after it finishes"""
        try:
            if hasattr(self, 'wifi_thread') and self.wifi_thread:
                try:
                    self.wifi_thread.deleteLater()
                except Exception:
                    pass
                self.wifi_thread = None
        except Exception:
            pass
    
    def _on_wifi_ready(self, wifi_name: str):
        """Handle WiFi name ready"""
        try:
            self.lbl_current_wifi.setText(wifi_name)
        except Exception:
            pass
    
    def _cleanup_connection_thread(self):
        """Clean up connection thread after it finishes"""
        try:
            if hasattr(self, 'connection_thread') and self.connection_thread:
                try:
                    self.connection_thread.deleteLater()
                except Exception:
                    pass
                self.connection_thread = None
        except Exception:
            pass
    
    def _test_hardware_connection(self):
        """Test connection to hardware simulator in background thread"""
        try:
            # Prevent multiple concurrent connection tests
            if hasattr(self, 'connection_thread') and self.connection_thread and self.connection_thread.isRunning():
                return  # Already testing, ignore new request
            
            # Start connection test in background thread
            self.connection_thread = ConnectionTestThread()
            self.connection_thread.connection_result.connect(self._on_connection_result)
            self.connection_thread.finished.connect(lambda: self._cleanup_connection_thread())
            self.connection_thread.start()
            
            # Show waiting status
            self.lbl_connection_status.setText("Testing connection...")
            self.lbl_connection_status.setStyleSheet("font-family: 'Segoe Print'; font-size: 16px; color: #003366; font-weight: 600;")
        except Exception as e:
            self.lbl_connection_status.setText(f"✗ Error")
            self.lbl_connection_status.setStyleSheet("font-family: 'Segoe Print'; font-size: 16px; color: #FF0000; font-weight: 700;")
    
    def _on_connection_result(self, success: bool, message: str):
        """Handle connection test result"""
        try:
            if success:
                # Green text for success
                self.lbl_connection_status.setText(f"✓ {message}")
                self.lbl_connection_status.setStyleSheet("font-family: 'Segoe Print'; font-size: 16px; color: #00AA00; font-weight: 700;")
            else:
                # Red text for failure
                self.lbl_connection_status.setText(f"✗ {message}")
                self.lbl_connection_status.setStyleSheet("font-family: 'Segoe Print'; font-size: 16px; color: #FF0000; font-weight: 700;")
        except Exception:
            pass
