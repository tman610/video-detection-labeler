from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QLabel, QSlider, QFileDialog, QFormLayout,
    QComboBox, QListWidget, QListWidgetItem, QLineEdit, QMessageBox,
    QInputDialog, QTextEdit, QDialog, QDialogButtonBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QImage, QShortcut, QKeySequence, QTextCursor
from video_display import VideoDisplay
import sys
import logging

# --- Training Log Dialog --- 
class TrainingLogDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Training Log")
        self.setMinimumSize(600, 400)
        
        layout = QVBoxLayout(self)
        self.log_text_edit = QTextEdit(self)
        self.log_text_edit.setReadOnly(True)
        layout.addWidget(self.log_text_edit)
        
        # Add stop button
        self.stop_button = QPushButton("Stop Training")
        self.stop_button.setEnabled(False)  # Initially disabled
        layout.addWidget(self.stop_button)
        
        # Make it non-modal so the main window can still be used
        self.setModal(False)
        
        # Store original stdout and stderr
        self.original_stdout = sys.stdout
        self.original_stderr = sys.stderr
        
        # Create our custom stream
        self.log_stream = LogStream(self)
        
        # Set up logging to capture all output
        self.setup_logging()

    def setup_logging(self):
        """Set up logging to capture all output"""
        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        
        # Create a handler that writes to our log stream
        self.log_handler = logging.StreamHandler(self.log_stream)
        self.log_handler.setLevel(logging.INFO)
        
        # Add the handler to the root logger
        root_logger.addHandler(self.log_handler)
        
        # Redirect stdout and stderr
        sys.stdout = self.log_stream
        sys.stderr = self.log_stream

    def restore_logging(self):
        """Restore original logging configuration"""
        # Remove our handler from the root logger
        root_logger = logging.getLogger()
        root_logger.removeHandler(self.log_handler)
        
        # Restore original stdout and stderr
        sys.stdout = self.original_stdout
        sys.stderr = self.original_stderr

    def showEvent(self, event):
        """Called when the dialog is shown"""
        super().showEvent(event)
        self.setup_logging()

    def closeEvent(self, event):
        """Called when the dialog is closed"""
        self.restore_logging()
        super().closeEvent(event)

    def append_text(self, text):
        """Appends text to the log and scrolls to the bottom."""
        self.log_text_edit.moveCursor(QTextCursor.End)
        self.log_text_edit.insertPlainText(text)
        self.log_text_edit.moveCursor(QTextCursor.End)
    
    def clear_text(self):
        self.log_text_edit.clear()

class LogStream:
    """A stream-like object that writes to the log dialog"""
    def __init__(self, dialog):
        self.dialog = dialog

    def write(self, text):
        if text.strip():  # Only send non-empty lines
            self.dialog.append_text(text)

    def flush(self):
        pass

    def isatty(self):
        return False

# --- Main Video View --- 
class VideoView(QMainWindow):
    # Add signals for new shortcuts
    navigate_labeled_up = Signal()
    navigate_labeled_down = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Video Labeling Tool")
        self.setMinimumSize(1200, 600)
        
        # Create the log dialog instance but don't show it yet
        self.training_log_dialog = TrainingLogDialog(self)
        
        # Create the main widget and layout
        self.main_widget = QWidget()
        self.setCentralWidget(self.main_widget)
        self.main_layout = QHBoxLayout(self.main_widget)
        
        # --- Video Panel --- 
        self.video_container = QWidget()
        self.video_layout = QVBoxLayout(self.video_container)
        
        # Create the video display
        self.video_display = VideoDisplay()
        self.video_display.setMinimumSize(600, 400)
        self.video_layout.addWidget(self.video_display)
        
        # Create the control panel for video
        self.control_panel = QWidget()
        self.control_layout = QVBoxLayout(self.control_panel)
        
        # Video Top Row: Cursor Pos, FPS, Speed
        self.video_top_row = QHBoxLayout()
        self.cursor_pos_label = QLabel("(0, 0)")
        self.fps_label = QLabel("FPS: 0")
        self.speed_dropdown = QComboBox()
        self.speed_dropdown.addItems(["1x", "2x", "3x", "4x", "5x", "10x"])
        self.video_top_row.addWidget(self.cursor_pos_label)
        self.video_top_row.addStretch()
        self.video_top_row.addWidget(self.fps_label)
        self.video_top_row.addWidget(self.speed_dropdown)
        self.control_layout.addLayout(self.video_top_row)
        
        # Video Frame Controls
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
        
        # Video Seek Bar
        self.seek_slider = QSlider(Qt.Horizontal)
        self.control_layout.addWidget(self.seek_slider)
        
        # Video Frame Counter
        self.frame_counter = QLabel("Frame: 0 / 0")
        self.control_layout.addWidget(self.frame_counter)
        
        # Add control panel to video container
        self.video_layout.addWidget(self.control_panel)
        
        # --- Form Panel (Right Side) --- 
        self.form_panel = QWidget()
        self.form_panel.setFixedWidth(400) # Adjusted width
        self.form_layout = QVBoxLayout(self.form_panel) # Changed to QVBoxLayout

        # Project Selection Area
        self.project_layout = QHBoxLayout()
        self.project_label = QLabel("Project:")
        self.project_dropdown = QComboBox()
        self.add_project_button = QPushButton("+")
        self.project_layout.addWidget(self.project_label)
        self.project_layout.addWidget(self.project_dropdown, 1) # Stretch dropdown
        self.project_layout.addWidget(self.add_project_button)
        self.form_layout.addLayout(self.project_layout)

        # Open Video Button (moved here)
        self.open_button = QPushButton("Open Video (Ctrl+O)")
        self.form_layout.addWidget(self.open_button)
        
        # Class Management Area
        # Remove the label and list widget
        # self.class_label = QLabel("Classes for Project:")
        # self.class_list = QListWidget()
        # self.class_list.setFixedHeight(100) # Limit height
        # self.form_layout.addWidget(self.class_label)
        # self.form_layout.addWidget(self.class_list)

        # Current Class Selection for Drawing
        self.current_class_layout = QHBoxLayout()
        self.current_class_label = QLabel("Label Class:")
        self.current_class_dropdown = QComboBox()
        self.add_current_class_button = QPushButton("+") # New button
        self.add_current_class_button.setFixedWidth(30) # Make it small
        self.current_class_layout.addWidget(self.current_class_label)
        self.current_class_layout.addWidget(self.current_class_dropdown, 1) # Stretch dropdown
        self.current_class_layout.addWidget(self.add_current_class_button) # Add the button
        self.form_layout.addLayout(self.current_class_layout)

        # Labeled Frames List Area
        self.labeled_frames_label = QLabel("Frames with Labels:")
        self.labeled_frames_list = QListWidget()
        # self.labeled_frames_list.setFixedHeight(150) # Or let it stretch
        self.form_layout.addWidget(self.labeled_frames_label)
        self.form_layout.addWidget(self.labeled_frames_list)

        # Export Button
        self.export_button = QPushButton("Export Dataset")
        self.form_layout.addWidget(self.export_button)

        # Train Button
        self.train_button = QPushButton("Train Model")
        self.form_layout.addWidget(self.train_button)

        # self.form_layout.addStretch() # Remove stretch to let list grow
        
        # Add the main panels to the main layout
        self.main_layout.addWidget(self.video_container, 2)  # Video takes more space
        self.main_layout.addWidget(self.form_panel, 1)      # Form panel takes less space
        
        # Set up keyboard shortcuts
        self._setup_shortcuts()
        
        # Connect signals for the view itself
        self.video_display.cursor_position_changed.connect(self.update_cursor_position)
    
    def _setup_shortcuts(self):
        """Set up keyboard shortcuts for video navigation and list navigation"""
        # Open Video Shortcut (New)
        open_video_shortcut = QShortcut(QKeySequence("Ctrl+O"), self)
        open_video_shortcut.activated.connect(lambda: self.open_button.click())

        # Left arrow: Previous frame
        prev_frame_shortcut = QShortcut(QKeySequence(Qt.Key_Left), self)
        prev_frame_shortcut.activated.connect(lambda: self.prev_frame.click())
        
        # Right arrow: Next frame
        next_frame_shortcut = QShortcut(QKeySequence(Qt.Key_Right), self)
        next_frame_shortcut.activated.connect(lambda: self.next_frame.click())
        
        # Shift+Left arrow: Previous 10 frames (Changed)
        prev_10_frames_shortcut = QShortcut(QKeySequence("Shift+Left"), self)
        # Restore original connection
        prev_10_frames_shortcut.activated.connect(lambda: self.prev_10_frames.click())
        
        # Shift+Right arrow: Next 10 frames (Changed)
        next_10_frames_shortcut = QShortcut(QKeySequence("Shift+Right"), self)
        # Restore original connection
        next_10_frames_shortcut.activated.connect(lambda: self.next_10_frames.click())
        
        # Space: Play/Pause
        play_pause_shortcut = QShortcut(QKeySequence(Qt.Key_Space), self)
        play_pause_shortcut.activated.connect(lambda: self.play_button.click())

        # Ctrl+Left arrow: Navigate Labeled Frames List Up (New)
        navigate_up_shortcut = QShortcut(QKeySequence("Ctrl+Left"), self)
        navigate_up_shortcut.activated.connect(self.navigate_labeled_up.emit)

        # Ctrl+Right arrow: Navigate Labeled Frames List Down (New)
        navigate_down_shortcut = QShortcut(QKeySequence("Ctrl+Right"), self)
        navigate_down_shortcut.activated.connect(self.navigate_labeled_down.emit)
    
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
        # Block signals temporarily to prevent feedback loop if model updates slider
        self.seek_slider.blockSignals(True)
        self.seek_slider.setRange(0, max(0, total_frames - 1)) # Ensure range is non-negative
        self.seek_slider.setValue(current_frame)
        self.seek_slider.blockSignals(False)
    
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
        else:
            self.cursor_pos_label.setText("(-, -)") # Indicate outside image
    
    def get_speed_multiplier(self):
        """Get the current speed multiplier from the dropdown"""
        text = self.speed_dropdown.currentText()
        try:
            return float(text.rstrip('x'))
        except ValueError:
            return 1.0 # Default to 1x if parsing fails

    def populate_project_dropdown(self, projects):
        """Populate the project dropdown with project data (id, name)"""
        self.project_dropdown.blockSignals(True)
        self.project_dropdown.clear()
        if not projects:
             self.project_dropdown.addItem("No projects found", -1)
        else:
            for project_id, name in projects:
                self.project_dropdown.addItem(name, project_id) # Store ID in userData
        self.project_dropdown.blockSignals(False)

    def get_selected_project_id(self):
        """Get the ID of the currently selected project"""
        return self.project_dropdown.currentData()

    def set_selected_project(self, project_id):
         """Set the currently selected project in the dropdown"""
         index = self.project_dropdown.findData(project_id)
         if index != -1:
             self.project_dropdown.setCurrentIndex(index)

    def get_new_project_name(self):
         """Prompt user for a new project name"""
         name, ok = QInputDialog.getText(self, "New Project", "Enter project name:")
         return name if ok and name else None

    def populate_current_class_dropdown(self, classes):
        """Populate the current class dropdown for drawing"""
        self.current_class_dropdown.blockSignals(True)
        self.current_class_dropdown.clear()
        if not classes:
            self.current_class_dropdown.addItem("No classes available", -1)
        else:
             for class_id, name in classes:
                self.current_class_dropdown.addItem(name, class_id) # Store ID in userData
        self.current_class_dropdown.blockSignals(False)

    def get_selected_class_id(self):
        """Get the ID of the currently selected class for drawing"""
        return self.current_class_dropdown.currentData()

    def get_new_class_name(self):
        """Prompt user for a new class name"""
        name, ok = QInputDialog.getText(self, "New Class", "Enter class name:")
        return name if ok and name else None

    def populate_labeled_frames_list(self, frame_numbers):
        """Populate the list with frame numbers that have labels"""
        current_selection = self.labeled_frames_list.currentRow()
        current_frame_data = self.labeled_frames_list.currentItem().data(Qt.UserRole) if self.labeled_frames_list.currentItem() else None

        self.labeled_frames_list.clear()
        new_row_map = {}
        row_index = 0
        for frame_num in sorted(frame_numbers): # Ensure sorted order
            item = QListWidgetItem(str(frame_num))
            item.setData(Qt.UserRole, frame_num) # Store frame number in data
            self.labeled_frames_list.addItem(item)
            new_row_map[frame_num] = row_index
            row_index += 1

        # Try to restore selection
        if current_frame_data in new_row_map:
            self.labeled_frames_list.setCurrentRow(new_row_map[current_frame_data])
        elif current_selection != -1 and current_selection < self.labeled_frames_list.count():
             self.labeled_frames_list.setCurrentRow(current_selection) # Fallback to old index if possible

    def clear_labeled_frames_list(self):
        """Clear the list of labeled frames"""
        self.labeled_frames_list.clear()

    def show_error_message(self, title, message):
        """Display an error message box"""
        QMessageBox.critical(self, title, message)

    def show_info_message(self, title, message):
        """Display an informational message box"""
        QMessageBox.information(self, title, message)

    # --- Methods to handle list navigation (called by Controller) ---
    def select_labeled_frame_item(self, row_index):
        """Selects the item at the given row index in the labeled frames list."""
        if 0 <= row_index < self.labeled_frames_list.count():
            self.labeled_frames_list.setCurrentRow(row_index)
            # Ensure the selected item is visible
            self.labeled_frames_list.scrollToItem(self.labeled_frames_list.item(row_index))
            return self.labeled_frames_list.item(row_index)
        return None

    def get_current_labeled_frame_index(self):
        """Returns the row index of the currently selected item, or -1 if none."""
        return self.labeled_frames_list.currentRow()

    def get_labeled_frame_count(self):
        """Returns the number of items in the labeled frames list."""
        return self.labeled_frames_list.count() 
    # --- Log Dialog Methods --- 
    def show_log_dialog(self):
        self.training_log_dialog.show()
        self.training_log_dialog.raise_() # Bring to front
        self.training_log_dialog.activateWindow()

    def append_log_text(self, text):
        self.training_log_dialog.append_text(text)
        
    def clear_log_dialog(self):
        self.training_log_dialog.clear_text() 
