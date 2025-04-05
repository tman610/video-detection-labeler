from PySide6.QtCore import QTimer

class VideoController:
    def __init__(self, model, view):
        self.model = model
        self.view = view
        self.timer = QTimer()
        self.timer.timeout.connect(self._on_timer_timeout)
        
        # Connect view signals
        self.view.open_button.clicked.connect(self.open_video)
        self.view.play_button.clicked.connect(self.toggle_playback)
        self.view.prev_frame.clicked.connect(lambda: self.model.seek(self.model.current_frame_index - 1))
        self.view.next_frame.clicked.connect(self.model.advance_frame)
        self.view.prev_10_frames.clicked.connect(lambda: self.model.seek(self.model.current_frame_index - 10))
        self.view.next_10_frames.clicked.connect(lambda: self.model.seek(self.model.current_frame_index + 10))
        self.view.seek_slider.sliderMoved.connect(self.model.seek)
        
        # Connect model signals
        self.model.frame_changed.connect(self.view.display_frame)
        self.model.frame_count_changed.connect(self._on_frame_count_changed)
        self.model.current_frame_index_changed.connect(self._on_current_frame_changed)
        self.model.playback_state_changed.connect(self._on_playback_state_changed)
        self.model.fps_changed.connect(self.view.update_fps)
    
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
        else:
            self.timer.stop()
    
    def _on_timer_timeout(self):
        """Handle timer timeout for frame advancement"""
        self.model.advance_frame()
    
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