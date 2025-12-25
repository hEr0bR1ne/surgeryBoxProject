"""
QuizModule: Reusable module for displaying and handling quiz questions.
"""
import json
import os
import random
from PySide6.QtCore import Qt, QUrl, QTimer, Signal
from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QWidget, QSizePolicy
)
from PySide6.QtGui import QFont
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput


class QuizModule(QFrame):
    """Quiz module for displaying and handling multiple choice questions."""
    
    quiz_completed = Signal()  # Signal when all questions are completed
    back_clicked = Signal()  # Signal when back button is clicked
    
    def __init__(self, parent=None, training_mode=False):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        
        # Quiz state
        self.questions = {}
        self.question_queue = []  # List of question IDs to display in order
        self.current_question_index = 0
        self.selected_answers = {}  # {question_id: [selected_options]}
        self.error_count = 0  # Count errors for current question (max 3)
        self.first_attempt_correct = {}  # Track if first attempt was correct
        self.training_mode = training_mode  # Flag for training mode (no score display)
        
        # Audio players
        self.audio_player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.audio_player.setAudioOutput(self.audio_output)
        
        # Timers
        self.question_audio_timer = None
        self.feedback_timer = None
        
        # UI Components
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(18, 18, 18, 18)
        self.main_layout.setSpacing(12)
        
        # Question number and title
        self.lbl_question_num = QLabel("")
        self.lbl_question_num.setStyleSheet("""
            font-family: 'Segoe Print', 'Segoe UI', Arial;
            font-size: 20px;
            font-weight: 700;
            color: #003366;
        """)
        self.main_layout.addWidget(self.lbl_question_num)
        
        # Question text
        self.lbl_question = QLabel("")
        self.lbl_question.setWordWrap(True)
        # Allow question label to expand horizontally so long questions are visible
        self.lbl_question.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.lbl_question.setMinimumWidth(600)
        self.lbl_question.setStyleSheet("""
            font-family: 'Segoe Print', 'Segoe UI', Arial;
            font-size: 18px;
            color: #003366;
            background: rgba(255, 255, 255, 0.5);
            padding: 12px;
            border-radius: 6px;
        """)
        self.main_layout.addWidget(self.lbl_question)
        
        # Options container
        self.options_frame = QFrame()
        self.options_frame.setStyleSheet("background: transparent;")
        self.options_layout = QVBoxLayout(self.options_frame)
        self.options_layout.setSpacing(8)
        self.options_layout.setContentsMargins(0, 0, 0, 0)
        if self.training_mode:
            self.options_layout.addStretch()  # Add stretch at top to push options down (training only)
        self.main_layout.addWidget(self.options_frame, 1)  # Give it stretch factor
        
        # Feedback label
        self.lbl_feedback = QLabel("")
        self.lbl_feedback.setWordWrap(True)
        self.lbl_feedback.setStyleSheet("""
            font-family: 'Segoe Print', 'Segoe UI', Arial;
            font-size: 18px;
            font-weight: 700;
            color: #003366;
            background: rgba(255, 255, 255, 0);
            padding: 12px;
        """)
        self.lbl_feedback.setVisible(False)
        self.main_layout.addWidget(self.lbl_feedback)
        
        # Button container
        button_container = QFrame()
        button_container.setStyleSheet("background: transparent;")
        button_layout = QHBoxLayout(button_container)
        button_layout.setSpacing(12)
        button_layout.setContentsMargins(0, 0, 0, 0)
        
        # Back button
        self.btn_back = QPushButton("← Back")
        self.btn_back.setStyleSheet("""
            QPushButton {
                background: rgba(200, 200, 200, 0.3);
                border: 2px solid #999999;
                border-radius: 8px;
                padding: 8px 16px;
                font-family: 'Segoe Print';
                font-size: 14px;
                font-weight: 600;
                color: #003366;
                min-width: 100px;
            }
            QPushButton:hover { background: rgba(200, 200, 200, 0.4); }
            QPushButton:pressed { background: rgba(200, 200, 200, 0.5); }
        """)
        self.btn_back.clicked.connect(self._on_back_clicked)
        button_layout.addWidget(self.btn_back)
        
        # Skip button
        self.btn_skip = QPushButton("Skip")
        self.btn_skip.setStyleSheet("""
            QPushButton {
                background: rgba(255, 200, 0, 0.3);
                border: 2px solid #FFC800;
                border-radius: 8px;
                padding: 8px 16px;
                font-family: 'Segoe Print';
                font-size: 14px;
                font-weight: 600;
                color: #003366;
                min-width: 100px;
            }
            QPushButton:hover { background: rgba(255, 200, 0, 0.4); }
            QPushButton:pressed { background: rgba(255, 200, 0, 0.5); }
        """)
        self.btn_skip.clicked.connect(self._on_skip_clicked)
        button_layout.addWidget(self.btn_skip)
        
        # Submit button
        self.btn_submit = QPushButton("Submit")
        self.btn_submit.setStyleSheet("""
            QPushButton {
                background: rgba(77, 163, 255, 0.3);
                border: 2px solid #4DA3FF;
                border-radius: 8px;
                padding: 10px 20px;
                font-family: 'Segoe Print';
                font-size: 16px;
                font-weight: 700;
                color: #003366;
                min-width: 120px;
            }
            QPushButton:hover { background: rgba(77, 163, 255, 0.4); }
            QPushButton:pressed { background: rgba(77, 163, 255, 0.5); }
        """)
        self.btn_submit.clicked.connect(self._on_submit)
        button_layout.addWidget(self.btn_submit)
        
        # Next button (hidden initially)
        self.btn_next = QPushButton("Next")
        self.btn_next.setStyleSheet("""
            QPushButton {
                background: rgba(0, 170, 0, 0.3);
                border: 2px solid #00AA00;
                border-radius: 8px;
                padding: 10px 20px;
                font-family: 'Segoe Print';
                font-size: 16px;
                font-weight: 700;
                color: #003366;
                min-width: 120px;
            }
            QPushButton:hover { background: rgba(0, 170, 0, 0.4); }
            QPushButton:pressed { background: rgba(0, 170, 0, 0.5); }
        """)
        self.btn_next.clicked.connect(self._on_next_clicked)
        self.btn_next.setVisible(False)
        button_layout.addWidget(self.btn_next)
        
        button_layout.addStretch()
        self.main_layout.addWidget(button_container)
        
        self.main_layout.addStretch()
    
    def load_quiz_data(self, json_path):
        """Load quiz questions from JSON file."""
        if os.path.exists(json_path):
            with open(json_path, 'r', encoding='utf-8') as f:
                self.questions = json.load(f)
        else:
            print(f"Quiz file not found: {json_path}")
    
    def start_quiz(self, question_ids=None):
        """
        Start quiz with specified question IDs.
        If question_ids is None, use all questions.
        """
        if question_ids is None:
            question_ids = list(self.questions.keys())
        
        self.question_queue = question_ids
        self.current_question_index = 0
        self.selected_answers = {}
        
        self._display_current_question()
    
    def _display_current_question(self):
        """Display the current question."""
        if self.current_question_index >= len(self.question_queue):
            # Quiz completed
            self.quiz_completed.emit()
            return
        
        question_id = self.question_queue[self.current_question_index]
        question_data = self.questions[question_id]
        
        # Reset error count for new question
        self.error_count = 0
        
        # Update question number and text
        progress = f"{self.current_question_index + 1}/{len(self.question_queue)}"
        self.lbl_question_num.setText(f"{question_id} ({progress})")
        
        # Build question text with statements if available (for Q5)
        question_text = question_data["question"]
        if "statements" in question_data:
            question_text += "\n\n"
            for stmt_key in sorted(question_data["statements"].keys()):
                stmt_text = question_data["statements"][stmt_key]
                question_text += f"{stmt_key}: {stmt_text}\n"
        
        self.lbl_question.setText(question_text)
        
        # Clear previous answers
        self.selected_answers[question_id] = []
        
        # Clear feedback
        self.lbl_feedback.setVisible(False)
        self.lbl_feedback.setText("")
        
        # Reset button states
        self.btn_submit.setEnabled(True)
        self.btn_submit.setVisible(True)
        self.btn_skip.setEnabled(True)
        self.btn_skip.setVisible(True)
        self.btn_next.setVisible(False)
        
        # Clear and populate options
        while self.options_layout.count():
            widget = self.options_layout.takeAt(0).widget()
            if widget:
                widget.deleteLater()
        
        # Re-add stretch at beginning after clearing (only for training mode)
        if self.training_mode:
            self.options_layout.insertStretch(0, 0)
        
        # Determine if multiple answers are allowed
        is_multiple = len(question_data["correct_answers"]) > 1
        
        # Create option buttons
        for option_key in sorted(question_data["options"].keys()):
            option_text = question_data["options"][option_key]
            
            if isinstance(option_text, list):
                # Statement type (Q5) - option_text is a list of statement keys
                # e.g., ["i", "iv"] -> "A: i AND iv" (只显示key，不显示statement内容)
                option_display = f"{option_key}: {' AND '.join(option_text)}"
            else:
                option_display = f"{option_key}: {option_text}"
            
            btn = QPushButton(option_display)
            btn.setCheckable(True)
            btn.setMinimumHeight(60)
            btn.setStyleSheet("""
                QPushButton {
                    background: rgba(255, 255, 255, 0.6);
                    border: 2px solid #cccccc;
                    border-radius: 6px;
                    padding: 12px;
                    font-family: 'Segoe Print';
                    font-size: 14px;
                    text-align: left;
                    color: #003366;
                    white-space: pre-wrap;
                }
                QPushButton:hover {
                    background: rgba(255, 255, 255, 0.8);
                    border: 2px solid #4DA3FF;
                }
                QPushButton:checked {
                    background: rgba(77, 163, 255, 0.3);
                    border: 2px solid #4DA3FF;
                    font-weight: 700;
                }
            """)
            
            btn.clicked.connect(lambda checked, key=option_key, qid=question_id, multi=is_multiple:
                               self._on_option_clicked(key, qid, multi))
            
            self.options_layout.addWidget(btn)
            
            # Store button reference for later access
            if not hasattr(self, '_option_buttons'):
                self._option_buttons = {}
            self._option_buttons[option_key] = btn
        
        # Add stretch at end after buttons
        self.options_layout.addStretch()
        
        # Schedule audio playback
        self._schedule_question_audio(question_id)
    
    def _schedule_question_audio(self, question_id):
        """Schedule question audio to play after 1 second."""
        if self.question_audio_timer:
            self.question_audio_timer.stop()
        
        self.question_audio_timer = QTimer()
        self.question_audio_timer.setSingleShot(True)
        self.question_audio_timer.timeout.connect(lambda qid=question_id: self._play_question_audio(qid))
        self.question_audio_timer.start(1000)  # 1 second delay
    
    def _play_question_audio(self, question_id):
        """Play audio for the question (e.g., Q1.mp3)."""
        audio_path = os.path.join("assets", f"{question_id}.mp3")
        if os.path.exists(audio_path):
            self.audio_player.setSource(QUrl.fromLocalFile(os.path.abspath(audio_path)))
            self.audio_player.play()
    
    def _on_option_clicked(self, option_key, question_id, is_multiple):
        """Handle option button click."""
        if not is_multiple:
            # Single answer: deselect others
            for i in range(self.options_layout.count()):
                btn = self.options_layout.itemAt(i).widget()
                if isinstance(btn, QPushButton):
                    btn.setChecked(False)
            
            # Check the clicked button
            if hasattr(self, '_option_buttons') and option_key in self._option_buttons:
                self._option_buttons[option_key].setChecked(True)
            
            # Update selected answers - single choice
            self.selected_answers[question_id] = [option_key]
        else:
            # Multiple choice: toggle selection
            if option_key not in self.selected_answers[question_id]:
                self.selected_answers[question_id].append(option_key)
            else:
                self.selected_answers[question_id].remove(option_key)
    
    def _on_back_clicked(self):
        """Handle back button click."""
        # Stop audio if playing
        try:
            self.audio_player.stop()
        except Exception:
            pass
        
        # Stop feedback timer if running
        if self.feedback_timer:
            self.feedback_timer.stop()
        
        # Stop question audio timer if running
        if self.question_audio_timer:
            self.question_audio_timer.stop()
        
        # Emit signal to parent
        self.back_clicked.emit()
    
    def _on_skip_clicked(self):
        """Handle skip button click - show correct answer."""
        question_id = self.question_queue[self.current_question_index]
        question_data = self.questions[question_id]
        correct_answers = set(question_data["correct_answers"])
        
        # Mark correct answers as selected for display
        for i in range(self.options_layout.count()):
            btn = self.options_layout.itemAt(i).widget()
            if isinstance(btn, QPushButton):
                # Extract option key from button text
                button_text = btn.text()
                option_key = button_text.split(":")[0]
                
                if option_key in correct_answers:
                    btn.setChecked(True)
                    btn.setStyleSheet("""
                        QPushButton {
                            background: rgba(0, 170, 0, 0.3);
                            border: 2px solid #00AA00;
                            border-radius: 6px;
                            padding: 10px;
                            font-family: 'Segoe Print';
                            font-size: 16px;
                            text-align: left;
                            color: #003366;
                            font-weight: 700;
                        }
                        QPushButton:hover {
                            background: rgba(0, 170, 0, 0.3);
                            border: 2px solid #00AA00;
                        }
                        QPushButton:checked {
                            background: rgba(0, 170, 0, 0.3);
                            border: 2px solid #00AA00;
                            font-weight: 700;
                        }
                    """)
        
        # Show feedback
        self.lbl_feedback.setText("✓ Correct Answer (Skipped)")
        self.lbl_feedback.setStyleSheet("""
            font-family: 'Segoe Print', 'Segoe UI', Arial;
            font-size: 18px;
            font-weight: 700;
            color: #00AA00;
            background: rgba(200, 255, 200, 0.3);
            padding: 12px;
            border-radius: 6px;
        """)
        self.lbl_feedback.setVisible(True)
        
        # Disable submit and skip buttons, show next button
        self.btn_submit.setEnabled(False)
        self.btn_skip.setEnabled(False)
        self.btn_next.setVisible(True)
    
    def _on_next_clicked(self):
        """Handle next button click."""
        self.current_question_index += 1
        self._display_current_question()
    
    def _on_submit(self):
        """Handle submit button click."""
        question_id = self.question_queue[self.current_question_index]
        question_data = self.questions[question_id]
        
        # Get correct answers
        correct_answers = set(question_data["correct_answers"])
        selected_answers = set(self.selected_answers[question_id])
        
        # Track first attempt correctness
        if self.error_count == 0:  # First attempt
            self.first_attempt_correct[question_id] = (correct_answers == selected_answers)
        
        if correct_answers == selected_answers:
            # Correct answer
            self._show_success()
        else:
            # Incorrect answer
            self._show_error()
    
    def _show_success(self):
        """Show success feedback."""
        self.lbl_feedback.setText("✓ Correct! Well done!")
        self.lbl_feedback.setStyleSheet("""
            font-family: 'Segoe Print', 'Segoe UI', Arial;
            font-size: 18px;
            font-weight: 700;
            color: #00AA00;
            background: rgba(200, 255, 200, 0.3);
            padding: 12px;
            border-radius: 6px;
        """)
        self.lbl_feedback.setVisible(True)
        
        # Play success audio
        success_path = os.path.join("assets", "success.mp3")
        if os.path.exists(success_path):
            self.audio_player.setSource(QUrl.fromLocalFile(os.path.abspath(success_path)))
            self.audio_player.play()
        
        # Schedule next question after 2 seconds
        if self.feedback_timer:
            self.feedback_timer.stop()
        
        self.feedback_timer = QTimer()
        self.feedback_timer.setSingleShot(True)
        self.feedback_timer.timeout.connect(self._move_to_next_question)
        self.feedback_timer.start(2000)
    
    def _show_error(self):
        """Show error feedback with 3-strike limit."""
        self.error_count += 1
        
        if self.error_count >= 3:
            # Show correct answer after 3 wrong attempts
            self._show_correct_answer()
        else:
            # Show error and allow retry
            remaining = 3 - self.error_count
            self.lbl_feedback.setText(f"✗ Wrong answer. You have {remaining} more attempts.")
            self.lbl_feedback.setStyleSheet("""
                font-family: 'Segoe Print', 'Segoe UI', Arial;
                font-size: 18px;
                font-weight: 700;
                color: #FF0000;
                background: rgba(255, 200, 200, 0.3);
                padding: 12px;
                border-radius: 6px;
            """)
            self.lbl_feedback.setVisible(True)
            
            # Play fail audio
            fail_path = os.path.join("assets", "fail.mp3")
            if os.path.exists(fail_path):
                self.audio_player.setSource(QUrl.fromLocalFile(os.path.abspath(fail_path)))
                self.audio_player.play()
            
            # Reset selection for retry
            self._reset_current_question_selection()

    def _show_correct_answer(self):
        """Show the correct answer after 3 wrong attempts."""
        question_id = self.question_queue[self.current_question_index]
        question_data = self.questions[question_id]
        correct_answers = set(question_data["correct_answers"])
        
        # Mark correct answers as selected for display
        for i in range(self.options_layout.count()):
            btn = self.options_layout.itemAt(i).widget()
            if isinstance(btn, QPushButton):
                button_text = btn.text()
                option_key = button_text.split(":")[0]
                
                if option_key in correct_answers:
                    btn.setChecked(True)
                    btn.setStyleSheet("""
                        QPushButton {
                            background: rgba(0, 170, 0, 0.3);
                            border: 2px solid #00AA00;
                            border-radius: 6px;
                            padding: 10px;
                            font-family: 'Segoe Print';
                            font-size: 16px;
                            text-align: left;
                            color: #003366;
                            font-weight: 700;
                        }
                    """)
                else:
                    btn.setEnabled(False)
        
        self.lbl_feedback.setText("The correct answer is shown above.")
        self.lbl_feedback.setStyleSheet("""
            font-family: 'Segoe Print', 'Segoe UI', Arial;
            font-size: 18px;
            font-weight: 700;
            color: #FF8800;
            background: rgba(255, 220, 160, 0.3);
            padding: 12px;
            border-radius: 6px;
        """)
        self.lbl_feedback.setVisible(True)
        
        # Schedule next question after 3 seconds
        if self.feedback_timer:
            self.feedback_timer.stop()
        
        self.feedback_timer = QTimer()
        self.feedback_timer.setSingleShot(True)
        self.feedback_timer.timeout.connect(self._move_to_next_question)
        self.feedback_timer.start(3000)
    
    def _reset_current_question_selection(self):
        """Reset all option buttons for the current question."""
        for i in range(self.options_layout.count()):
            btn = self.options_layout.itemAt(i).widget()
            if isinstance(btn, QPushButton):
                btn.setChecked(False)
        
        question_id = self.question_queue[self.current_question_index]
        self.selected_answers[question_id] = []
    
    def _move_to_next_question(self):
        """Move to the next question."""
        self.current_question_index += 1
        self._display_current_question()
    
    def get_score(self):
        """Calculate quiz score based on first attempt only."""
        correct_count = 0
        for question_id in self.question_queue:
            # Use first_attempt_correct if available, otherwise check current answer
            if question_id in self.first_attempt_correct:
                if self.first_attempt_correct[question_id]:
                    correct_count += 1
            else:
                # Fallback to current answer check
                question_data = self.questions[question_id]
                correct_answers = set(question_data["correct_answers"])
                selected_answers = set(self.selected_answers.get(question_id, []))
                
                if correct_answers == selected_answers:
                    correct_count += 1
        
        return correct_count, len(self.question_queue)
