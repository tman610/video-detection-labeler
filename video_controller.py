from PySide6.QtCore import QTimer
import time

class VideoController:
    def __init__(self, model, view):
        self.model = model
        self.view = view
        self.timer = QTimer()
        self.timer.timeout.connect(self._on_timer_timeout)
        self.last_frame_time = 0
        
        # Connect view signals
        self.view.open_button.clicked.connect(self.open_video)
        self.view.play_button.clicked.connect(self.toggle_playback)
        self.view.prev_frame.clicked.connect(lambda: self.model.seek(self.model.current_frame_index - 1))
        self.view.next_frame.clicked.connect(self.model.advance_frame)
        self.view.prev_10_frames.clicked.connect(lambda: self.model.seek(self.model.current_frame_index - 10))
        self.view.next_10_frames.clicked.connect(lambda: self.model.seek(self.model.current_frame_index + 10))
        
        # Connect slider signals for both dragging and clicking
        self.view.seek_slider.sliderMoved.connect(self._on_slider_moved)
        self.view.seek_slider.sliderReleased.connect(self._on_slider_released)
        
        # Connect model signals
        self.model.frame_changed.connect(self.view.display_frame)
        self.model.frame_count_changed.connect(self._on_frame_count_changed)
        self.model.current_frame_index_changed.connect(self._on_current_frame_changed)
        self.model.playback_state_changed.connect(self._on_playback_state_changed)
        self.model.fps_changed.connect(self.view.update_fps)
        self.model.rectangles_changed.connect(self.view.video_display.set_rectangles)
        
        # Connect rectangle drawing signal
        self.view.video_display.rectangle_drawn.connect(self._on_rectangle_drawn)
    
    def open_video(self):
        """Handle opening a new video file"""
        file_path = self.view.get_open_file_path()
        if file_path:
            self.model.load_video(file_path)
    
    def toggle_playback(self):
        """Handle play/pause button click"""
        is_playing = self.model.toggle_playback()
        if is_playing:
            frame_rate = self.model.get_frame_rate()
            if frame_rate > 0:
                self.timer.start(1000 // frame_rate)
                self.last_frame_time = time.time()
        else:
            self.timer.stop()
    
    def _on_timer_timeout(self):
        """Handle timer timeout for frame advancement"""
        current_time = time.time()
        frame_duration = 1.0 / self.model.get_frame_rate()
        
        # Check if it's time for the next frame
        if current_time - self.last_frame_time >= frame_duration:
            self.model.advance_frame()
            self.last_frame_time = current_time
    
    def _on_frame_count_changed(self, frame_count):
        """Handle frame count changes"""
        self.view.update_seek_slider(0, frame_count - 1)
    
    def _on_current_frame_changed(self, frame_index):
        """Handle current frame index changes"""
        self.view.update_frame_counter(frame_index, self.model.frame_count)
        self.view.update_seek_slider(frame_index, self.model.frame_count - 1)
    
    def _on_playback_state_changed(self, is_playing):
        """Handle playback state changes"""
        self.view.update_play_button(is_playing)
        if not is_playing:
            self.timer.stop()
    
    def _on_slider_moved(self, value):
        """Handle slider movement (dragging)"""
        self.model.seek(value)
    
    def _on_slider_released(self):
        """Handle slider release (clicking)"""
        value = self.view.seek_slider.value()
        self.model.seek(value)
        
    def _on_rectangle_drawn(self, x1, y1, x2, y2):
        """Handle rectangle drawn signal"""
        # Save the rectangle to the database
        if self.model.video_id is not None:
            self.model.db.save_rectangle(
                self.model.video_id,
                self.model.current_frame_index,
                x1, y1, x2, y2
            )
            self.model.add_rectangle(x1, y1, x2, y2) 
            print(f"Rectangle saved to database for video {self.model.video_id}, frame {self.model.current_frame_index}") 
