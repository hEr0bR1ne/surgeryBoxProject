"""
Camera Manager Module
Handles camera detection, selection, and preview
"""

import os
from PySide6.QtCore import Qt, QTimer, QThread, Signal, QRect
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, 
    QPushButton, QFrame, QMessageBox
)
from PySide6.QtGui import QPixmap, QImage, QPainter, QPen, QColor
from PySide6.QtMultimedia import QMediaDevices, QMediaCaptureSession, QCamera
from PySide6.QtMultimediaWidgets import QVideoWidget

import cv2
import numpy as np


class CameraThread(QThread):
    """Thread to capture video frames from camera"""
    frame_ready = Signal(QImage)
    
    def __init__(self, camera_index=0):
        super().__init__()
        self.camera_index = camera_index
        self.is_running = True
        self.cap = None
    
    def run(self):
        """Capture frames from camera"""
        try:
            self.cap = cv2.VideoCapture(self.camera_index)
            if not self.cap.isOpened():
                return
            
            try:
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                self.cap.set(cv2.CAP_PROP_FPS, 60)  # 设置帧率为60fps
            except Exception:
                pass
            
            while self.is_running:
                try:
                    ret, frame = self.cap.read()
                    if not ret:
                        break
                    
                    # Convert BGR to RGB
                    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    h, w, ch = rgb_frame.shape
                    bytes_per_line = ch * w
                    qt_image = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
                    
                    if self.is_running:  # Check again before emitting
                        self.frame_ready.emit(qt_image)
                    
                    # 减少延迟到16ms以支持60fps
                    self.msleep(16)
                    
                except Exception as e:
                    print(f"Frame capture error: {e}")
                    if not self.is_running:
                        break
                    self.msleep(100)
                    
        except Exception as e:
            print(f"Camera initialization error: {e}")
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Safely release camera resources"""
        try:
            if self.cap is not None:
                self.cap.release()
                self.cap = None
        except Exception as e:
            print(f"Error releasing camera: {e}")
    
    def stop(self):
        """Stop camera capture"""
        try:
            print(f"[CameraThread.stop] Stopping camera thread")
            self.is_running = False
            self.cleanup()
            # PySide6 wait() 不支持timeout参数，改用 msleep 轮询
            max_wait = 20  # 2 seconds / 100ms = 20 iterations
            for i in range(max_wait):
                if not self.isRunning():
                    print(f"[CameraThread.stop] Thread stopped after {i*100}ms")
                    break
                self.msleep(100)
            else:
                print(f"[CameraThread.stop] Thread did not finish after 2 seconds")
        except Exception as e:
            print(f"[CameraThread.stop] Error stopping thread: {e}")


class CameraManager(QWidget):
    """Camera selection and preview widget"""
    camera_changed = Signal(int)  # Emits selected camera index
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_camera_index = 0
        self.camera_thread = None
        self.available_cameras = self._detect_cameras()
        
        self._build_ui()
    
    def _detect_cameras(self):
        """Detect available cameras on the system"""
        available_cameras = []
        for i in range(10):  # Check first 10 indices
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                available_cameras.append(i)
                cap.release()
        return available_cameras
    
    def _build_ui(self):
        """Build camera selection UI"""
        root = QVBoxLayout(self)
        root.setSpacing(12)
        root.setContentsMargins(0, 0, 0, 0)
        
        # Camera selection section
        selection_frame = QFrame()
        selection_frame.setStyleSheet("background: transparent;")
        selection_l = QHBoxLayout(selection_frame)
        selection_l.setSpacing(12)
        
        # Label: Current Camera
        lbl_current = QLabel("Current Camera:")
        lbl_current.setStyleSheet("font-family: 'Segoe Print'; font-size: 16px; color: #003366; font-weight: 700;")
        selection_l.addWidget(lbl_current)
        
        # Display current camera
        self.lbl_camera_name = QLabel(f"Camera {self.current_camera_index}")
        self.lbl_camera_name.setStyleSheet("font-family: 'Segoe Print'; font-size: 14px; color: #234f8d;")
        self.lbl_camera_name.setMinimumWidth(150)
        selection_l.addWidget(self.lbl_camera_name)
        
        selection_l.addSpacing(20)
        
        # Label: Select Camera
        lbl_select = QLabel("Select Camera:")
        lbl_select.setStyleSheet("font-family: 'Segoe Print'; font-size: 16px; color: #003366; font-weight: 700;")
        selection_l.addWidget(lbl_select)
        
        # Dropdown for camera selection
        self.combo_cameras = QComboBox()
        self.combo_cameras.setStyleSheet("""
            QComboBox {
                background: rgba(255,255,255,0.8);
                border: 1px solid #4DA3FF;
                border-radius: 6px;
                padding: 6px;
                font-family: 'Segoe Print';
                font-size: 14px;
                color: #003366;
                min-width: 200px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                image: none;
            }
        """)
        
        # Populate camera list
        for cam_idx in self.available_cameras:
            self.combo_cameras.addItem(f"Camera {cam_idx}", cam_idx)
        
        self.combo_cameras.currentIndexChanged.connect(self._on_camera_selected)
        selection_l.addWidget(self.combo_cameras)
        
        # Confirm button
        btn_confirm = QPushButton("Confirm")
        btn_confirm.setStyleSheet("""
            QPushButton {
                background: rgba(77, 163, 255, 0.3);
                border: 2px solid #4DA3FF;
                border-radius: 6px;
                padding: 8px 16px;
                font-family: 'Segoe Print';
                font-size: 14px;
                font-weight: 600;
                color: #003366;
                min-width: 80px;
            }
            QPushButton:hover {
                background: rgba(77, 163, 255, 0.4);
            }
            QPushButton:pressed {
                background: rgba(77, 163, 255, 0.5);
            }
        """)
        btn_confirm.clicked.connect(self._confirm_camera)
        selection_l.addWidget(btn_confirm)
        
        selection_l.addStretch()
        root.addWidget(selection_frame)
        
        # Test button
        test_frame = QFrame()
        test_frame.setStyleSheet("background: transparent;")
        test_l = QHBoxLayout(test_frame)
        test_l.setSpacing(12)
        
        btn_test = QPushButton("Test Camera")
        btn_test.setStyleSheet("""
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
            QPushButton:hover {
                background: rgba(77, 163, 255, 0.4);
            }
            QPushButton:pressed {
                background: rgba(77, 163, 255, 0.5);
            }
        """)
        btn_test.clicked.connect(self._toggle_preview)
        test_l.addWidget(btn_test)
        
        self.btn_test = btn_test  # Store reference for toggling text
        
        # Alignment instruction - BEFORE preview
        lbl_instruction = QLabel("Please align the screen center blue dot with the simulator's epidural catheter entry point")
        lbl_instruction.setStyleSheet("font-family: 'Segoe Print'; font-size: 14px; color: #003366; font-weight: 600;")
        lbl_instruction.setWordWrap(True)
        lbl_instruction.setAlignment(Qt.AlignCenter)
        test_l.addWidget(lbl_instruction)
        
        # Setup complete button
        btn_setup_complete = QPushButton("Setup Complete")
        btn_setup_complete.setStyleSheet("""
            QPushButton {
                background: rgba(77, 163, 255, 0.3);
                border: 2px solid #4DA3FF;
                border-radius: 6px;
                padding: 6px 12px;
                font-family: 'Segoe Print';
                font-size: 12px;
                font-weight: 600;
                color: #003366;
                min-width: 80px;
            }
            QPushButton:hover {
                background: rgba(77, 163, 255, 0.4);
            }
            QPushButton:pressed {
                background: rgba(77, 163, 255, 0.5);
            }
        """)
        btn_setup_complete.clicked.connect(self._show_setup_complete)
        test_l.addWidget(btn_setup_complete)
        
        test_l.addStretch()
        root.addWidget(test_frame)
        
        # Camera preview
        self.preview_label = QLabel()
        self.preview_label.setStyleSheet("""
            QLabel {
                background: #000000;
                border: 2px solid #4DA3FF;
                border-radius: 6px;
                min-height: 500px;
                max-height: 500px;
                min-width: 600px;
            }
        """)
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setText("Camera preview will appear here")
        self.preview_label.setStyleSheet("""
            QLabel {
                background: #000000;
                border: 2px solid #4DA3FF;
                border-radius: 6px;
                min-height: 500px;
                max-height: 500px;
                min-width: 600px;
                color: white;
                font-family: 'Segoe Print';
                font-size: 14px;
            }
        """)
        root.addWidget(self.preview_label)
        
        root.addStretch()
    
    def _on_camera_selected(self, index):
        """Handle camera selection change"""
        if index >= 0:
            camera_idx = self.combo_cameras.itemData(index)
            self.current_camera_index = camera_idx
    
    def _confirm_camera(self):
        """Confirm camera selection"""
        self.lbl_camera_name.setText(f"Camera {self.current_camera_index}")
        self.camera_changed.emit(self.current_camera_index)
        # Stop preview if running
        if self.camera_thread and self.camera_thread.isRunning():
            self._toggle_preview()
    
    def _toggle_preview(self):
        """Toggle camera preview on/off"""
        try:
            if self.camera_thread and self.camera_thread.isRunning():
                # Stop preview
                try:
                    self.camera_thread.stop()
                except Exception as e:
                    print(f"Error stopping thread: {e}")
                finally:
                    self.camera_thread = None
                
                self.btn_test.setText("Test Camera")
                self.preview_label.setText("Camera preview will appear here")
                self.preview_label.setStyleSheet("""
                    QLabel {
                        background: #000000;
                        border: 2px solid #4DA3FF;
                        border-radius: 6px;
                        min-height: 500px;
                        max-height: 500px;
                        min-width: 600px;
                        color: white;
                        font-family: 'Segoe Print';
                        font-size: 14px;
                    }
                """)
            else:
                # Start preview
                try:
                    self.camera_thread = CameraThread(self.current_camera_index)
                    self.camera_thread.frame_ready.connect(self._update_preview)
                    self.camera_thread.start()
                    self.btn_test.setText("Stop Preview")
                except Exception as e:
                    print(f"Error starting camera preview: {e}")
                    self.preview_label.setText(f"Error: {str(e)}")
        except Exception as e:
            print(f"Unexpected error in _toggle_preview: {e}")
    
    def _update_preview(self, qt_image):
        """Update preview display with new frame and draw crosshair"""
        try:
            # Create pixmap from QImage
            pixmap = QPixmap.fromImage(qt_image)
            
            # Scale to fit label
            scaled = pixmap.scaledToHeight(500, Qt.SmoothTransformation)
            
            # Create a painter to draw crosshair on the scaled pixmap
            painter = QPainter(scaled)
            
            # Draw blue crosshair at center
            center_x = scaled.width() // 2
            center_y = scaled.height() // 2
            crosshair_size = 40
            thickness = 3
            
            # Set blue pen color
            pen = QPen(QColor(0, 0, 255))  # Blue
            pen.setWidth(thickness)
            painter.setPen(pen)
            
            # Vertical line
            painter.drawLine(center_x, center_y - crosshair_size, center_x, center_y + crosshair_size)
            # Horizontal line
            painter.drawLine(center_x - crosshair_size, center_y, center_x + crosshair_size, center_y)
            # Center circle
            painter.drawEllipse(center_x - 8, center_y - 8, 16, 16)
            
            painter.end()
            
            # Display the pixmap
            self.preview_label.setPixmap(scaled)
        except Exception as e:
            print(f"Error updating preview: {e}")
    
    def get_current_camera(self):
        """Get currently selected camera index"""
        return self.current_camera_index
    
    def cleanup(self):
        """Clean up resources"""
        try:
            if self.camera_thread:
                try:
                    if self.camera_thread.isRunning():
                        self.camera_thread.stop()
                except Exception:
                    pass
                finally:
                    self.camera_thread = None
        except Exception as e:
            print(f"Error during cleanup: {e}")
    
    def _show_setup_complete(self):
        """Show setup complete message for 2 seconds"""
        try:
            # Create message box
            msg = QMessageBox(self)
            msg.setWindowTitle("Setup Complete")
            msg.setText("✓ Setup Successful")
            msg.setStyleSheet("""
                QMessageBox {
                    background-color: rgba(255, 255, 255, 0.95);
                }
                QMessageBox QLabel {
                    color: #003366;
                    font-family: 'Segoe Print';
                    font-size: 16px;
                    font-weight: 700;
                }
                QPushButton {
                    background: rgba(77, 163, 255, 0.3);
                    border: 2px solid #4DA3FF;
                    border-radius: 6px;
                    padding: 6px 20px;
                    color: #003366;
                    font-family: 'Segoe Print';
                    font-size: 14px;
                    min-width: 60px;
                }
                QPushButton:hover {
                    background: rgba(77, 163, 255, 0.4);
                }
            """)
            
            # Show the message box in a non-blocking way
            msg.show()
            
            # Auto-close after 2 seconds
            QTimer.singleShot(2000, msg.close)
        except Exception as e:
            print(f"Error showing setup complete message: {e}")
