from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QLabel, QSlider, QFileDialog, QFormLayout
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QShortcut, QKeySequence
from video_display import VideoDisplay

class VideoView(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Video Player")
        self.setMinimumSize(1200, 600)
        
        # Create the main widget and layout
        self.main_widget = QWidget()
        self.setCentralWidget(self.main_widget)
        self.main_layout = QHBoxLayout(self.main_widget)
        
        # Create the video container widget
        self.video_container = QWidget()
        self.video_layout = QVBoxLayout(self.video_container)
        
        # Create the video display
        self.video_display = VideoDisplay()
        self.video_display.setMinimumSize(600, 400)
        self.video_layout.addWidget(self.video_display)
        
        # Create the control panel
        self.control_panel = QWidget()
        self.control_layout = QVBoxLayout(self.control_panel)
        
        # Create the top row with open button and FPS label
        self.top_row = QHBoxLayout()
        self.cursor_pos_label = QLabel("(0, 0)")
        self.open_button = QPushButton("Open Video")
        self.fps_label = QLabel("FPS: 0")
        self.top_row.addWidget(self.cursor_pos_label)
        self.top_row.addWidget(self.open_button)
        self.top_row.addStretch()
        self.top_row.addWidget(self.fps_label)
        self.control_layout.addLayout(self.top_row)
        
        # Create the frame controls
        self.frame_controls = QHBoxLayout()
        self.prev_10_frames = QPushButton("⏪⏪")
        self.prev_10_frames.setFixedHeight(30)
        self.prev_frame = QPushButton("⏪")
        self.prev_frame.setFixedHeight(30)
        self.play_button = QPushButton("▶")
        self.play_button.setFixedHeight(30)
        self.next_frame = QPushButton("⏩")
        self.next_frame.setFixedHeight(30)
        self.next_10_frames = QPushButton("⏩⏩")
        self.next_10_frames.setFixedHeight(30)
        
        self.frame_controls.addWidget(self.prev_10_frames)
        self.frame_controls.addWidget(self.prev_frame)
        self.frame_controls.addWidget(self.play_button)
        self.frame_controls.addWidget(self.next_frame)
        self.frame_controls.addWidget(self.next_10_frames)
        
        self.control_layout.addLayout(self.frame_controls)
        
        # Create the seek bar
        self.seek_slider = QSlider(Qt.Horizontal)
        self.control_layout.addWidget(self.seek_slider)
        
        # Create the frame counter
        self.frame_counter = QLabel("Frame: 0 / 0")
        self.control_layout.addWidget(self.frame_counter)
        
        # Add the control panel to the video container
        self.video_layout.addWidget(self.control_panel)
        
        # Create the form panel
        self.form_panel = QWidget()
        self.form_panel.setFixedWidth(600)
        self.form_layout = QFormLayout(self.form_panel)
        
        # Add the open button to the form
        self.form_layout.addRow("", self.open_button)
        
        # Add the panels to the main layout
        self.main_layout.addWidget(self.video_container, 2)  # 2/3 of the space
        self.main_layout.addWidget(self.form_panel, 1)      # 1/3 of the space
        
        # Set up keyboard shortcuts
        self._setup_shortcuts()
        
        # Connect the cursor position signal
        self.video_display.cursor_position_changed.connect(self.update_cursor_position)
    
    def _setup_shortcuts(self):
        """Set up keyboard shortcuts for video navigation"""
        # Left arrow: Previous frame
        prev_frame_shortcut = QShortcut(QKeySequence(Qt.Key_Left), self)
        prev_frame_shortcut.activated.connect(lambda: self.prev_frame.click())
        
        # Right arrow: Next frame
        next_frame_shortcut = QShortcut(QKeySequence(Qt.Key_Right), self)
        next_frame_shortcut.activated.connect(lambda: self.next_frame.click())
        
        # Ctrl+Left arrow: Previous 10 frames
        prev_10_frames_shortcut = QShortcut(QKeySequence("Ctrl+Left"), self)
        prev_10_frames_shortcut.activated.connect(lambda: self.prev_10_frames.click())
        
        # Ctrl+Right arrow: Next 10 frames
        next_10_frames_shortcut = QShortcut(QKeySequence("Ctrl+Right"), self)
        next_10_frames_shortcut.activated.connect(lambda: self.next_10_frames.click())
        
        # Space: Play/Pause
        play_pause_shortcut = QShortcut(QKeySequence(Qt.Key_Space), self)
        play_pause_shortcut.activated.connect(lambda: self.play_button.click())
    
    def get_open_file_path(self):
        """Open a file dialog to select a video file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open Video File", "", "Video Files (*.mp4 *.avi *.mov *.mkv);;All Files (*)"
        )
        return file_path
    
    def display_frame(self, frame):
        """Display a frame in the video display"""
        self.video_display.display_frame(frame)
    
    def update_frame_counter(self, current_frame, total_frames):
        """Update the frame counter label"""
        self.frame_counter.setText(f"Frame: {current_frame} / {total_frames}")
    
    def update_seek_slider(self, current_frame, total_frames):
        """Update the seek slider"""
        self.seek_slider.setRange(0, total_frames)
        self.seek_slider.setValue(current_frame)
    
    def update_play_button(self, is_playing):
        """Update the play button text based on playback state"""
        self.play_button.setText("⏸" if is_playing else "▶")
    
    def update_fps(self, fps):
        """Update the FPS label"""
        self.fps_label.setText(f"FPS: {fps:.2f}")
    
    def update_cursor_position(self, x, y):
        """Update the cursor position label"""
        if x >= 0 and y >= 0:
            self.cursor_pos_label.setText(f"({x}, {y})") 