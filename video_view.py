from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                              QPushButton, QFileDialog, QLabel, QSlider, QFrame)
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap, QKeySequence, QShortcut

class VideoView(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Video Player")
        self.setMinimumSize(1200, 600)
        
        # Create main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QHBoxLayout(main_widget)
        
        # Video display area (left side)
        video_container = QWidget()
        video_layout = QVBoxLayout(video_container)
        
        # Video display
        self.video_label = QLabel()
        self.video_label.setMinimumSize(600, 500)
        self.video_label.setStyleSheet("background-color: black;")
        video_layout.addWidget(self.video_label)
        
        # Video controls below video
        controls_container = QWidget()
        controls_layout = QVBoxLayout(controls_container)
        
        # Frame controls
        frame_controls = QHBoxLayout()
        self.prev_10_frames = QPushButton("<< 10 (Ctrl+←)")
        self.prev_frame = QPushButton("< 1 (←)")
        self.play_button = QPushButton("Play (Space)")
        self.next_frame = QPushButton("1 > (→)")
        self.next_10_frames = QPushButton("10 >> (Ctrl+→)")
        
        frame_controls.addWidget(self.prev_10_frames)
        frame_controls.addWidget(self.prev_frame)
        frame_controls.addWidget(self.play_button)
        frame_controls.addWidget(self.next_frame)
        frame_controls.addWidget(self.next_10_frames)
        controls_layout.addLayout(frame_controls)
        
        # Seek bar
        self.seek_slider = QSlider(Qt.Horizontal)
        controls_layout.addWidget(self.seek_slider)
        
        # Frame counter and FPS
        info_row = QHBoxLayout()
        self.frame_counter = QLabel("Frame: 0 / 0")
        self.fps_label = QLabel("FPS: 0")
        info_row.addWidget(self.frame_counter)
        info_row.addStretch()
        info_row.addWidget(self.fps_label)
        controls_layout.addLayout(info_row)
        
        video_layout.addWidget(controls_container)
        layout.addWidget(video_container)
        
        # Form panel (right side)
        form_panel = QFrame()
        form_panel.setFixedWidth(600)
        form_layout = QVBoxLayout(form_panel)
        
        # Open video button
        self.open_button = QPushButton("Open Video")
        form_layout.addWidget(self.open_button)
        
        # Add form panel to main layout
        layout.addWidget(form_panel)
        
        # Setup shortcuts
        self._setup_shortcuts()
    
    def _setup_shortcuts(self):
        """Setup keyboard shortcuts"""
        # Single frame navigation
        QShortcut(QKeySequence(Qt.Key_Left), self, self.prev_frame.click)
        QShortcut(QKeySequence(Qt.Key_Right), self, self.next_frame.click)
        
        # 10-frame navigation
        QShortcut(QKeySequence("Ctrl+Left"), self, self.prev_10_frames.click)
        QShortcut(QKeySequence("Ctrl+Right"), self, self.next_10_frames.click)
        
        # Play/Pause
        QShortcut(QKeySequence(Qt.Key_Space), self, self.play_button.click)
    
    def display_frame(self, frame):
        """Display a frame in the video label"""
        if frame is None:
            return
            
        # Convert frame to RGB
        frame_array = frame.to_ndarray(format='rgb24')
        height, width, _ = frame_array.shape
        bytes_per_line = 3 * width
        image = QImage(frame_array.data, width, height, bytes_per_line, QImage.Format_RGB888)
        
        # Scale image to fit the label while maintaining aspect ratio
        scaled_pixmap = QPixmap.fromImage(image).scaled(
            self.video_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.video_label.setPixmap(scaled_pixmap)
    
    def update_frame_counter(self, current_frame, total_frames):
        """Update the frame counter display"""
        self.frame_counter.setText(f"Frame: {current_frame} / {total_frames}")
    
    def update_seek_slider(self, value, maximum):
        """Update the seek slider"""
        self.seek_slider.setMaximum(maximum)
        self.seek_slider.setValue(value)
    
    def update_play_button(self, is_playing):
        """Update the play button text"""
        self.play_button.setText("Pause" if is_playing else "Play")
    
    def update_fps(self, fps):
        """Update the FPS display"""
        self.fps_label.setText(f"FPS: {fps:.2f}")
    
    def get_open_file_path(self):
        """Show file dialog and return selected file path"""
        file_name, _ = QFileDialog.getOpenFileName(
            self, "Open Video File", "",
            "Video Files (*.mp4 *.avi *.mkv)")
        return file_name 