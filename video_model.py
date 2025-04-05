import av
from PySide6.QtCore import QObject, Signal
import datetime
import os
from database import Database

class VideoModel(QObject):
    # Signals
    frame_changed = Signal(object)  # Emits the current frame
    frame_count_changed = Signal(int)  # Emits the total frame count
    current_frame_index_changed = Signal(int)  # Emits the current frame index
    playback_state_changed = Signal(bool)  # Emits the playing state
    fps_changed = Signal(float)  # Emits the current FPS
    
    def __init__(self):
        super().__init__()
        self.container = None
        self.stream = None
        self.current_frame = None
        self.frame_count = 0
        self.current_frame_index = 0
        self.is_playing = False
        self.frame_generator = None
        self.first_frame_pts = None
        self.frame_duration = None
        self.video_id = None
        self.video_name = None
        self.db = Database()
    
    def load_video(self, file_path):
        """Load a video file and initialize the model"""
        try:
            self.container = av.open(file_path)
            self.stream = self.container.streams.video[0]
            
            # Try to get frame count from stream frames
            self.frame_count = self.stream.frames if self.stream.frames is not None else 0
            
            # If frames is None or 0, try to get from metadata
            if not self.frame_count:
                self.frame_count = int(self.stream.metadata.get('NUMBER_OF_FRAMES-eng', '0'))
            
            # If still 0, try to calculate from duration
            if not self.frame_count:
                duration_str = self.stream.metadata.get('DURATION', '')
                if duration_str:
                    try:
                        # Split by colon to get hours, minutes, seconds
                        parts = duration_str.split(':')
                        if len(parts) == 3:
                            hours = float(parts[0])
                            minutes = float(parts[1])
                            seconds = float(parts[2])
                            total_seconds = hours * 3600 + minutes * 60 + seconds
                            # Calculate frame count from duration and frame rate
                            self.frame_count = int(total_seconds * self.stream.average_rate)
                    except (ValueError, IndexError):
                        print(f"Error parsing duration string: {duration_str}")
            
            # If all methods failed, use a default value
            if not self.frame_count:
                self.frame_count = 1000  # Default fallback
            
            print(f"Frame count: {self.frame_count}")
            print(f"Stream metadata: {self.stream.metadata}")
            
            # Store video information in the database
            self.video_name = os.path.basename(file_path)
            fps = float(self.get_frame_rate())  # Ensure fps is float
            frame_count = int(self.frame_count)  # Ensure frame_count is int
            
            # Store in database and get video ID
            self.video_id = self.db.get_or_create_video(self.video_name, fps, frame_count)
            print(f"Video ID: {self.video_id}")
            
            self.current_frame_index = 0
            self.frame_count_changed.emit(self.frame_count)
            self.fps_changed.emit(fps)
            
            # Get the first frame to store its PTS
            self.frame_generator = self.container.decode(video=0)
            try:
                first_frame = next(self.frame_generator)
                self.first_frame_pts = first_frame.pts
                # Calculate frame duration from stream time base
                self.frame_duration = int(self.stream.time_base.denominator / 
                                        (self.stream.time_base.numerator * self.stream.average_rate))
                self.current_frame = first_frame
                self.frame_changed.emit(self.current_frame)
                self.current_frame_index_changed.emit(self.current_frame_index)
            except StopIteration:
                self.reset_to_start()
                
        except Exception as e:
            print(f"Error loading video: {e}")
            self.cleanup()
    
    def _load_frame(self):
        """Load the current frame"""
        if self.container is None or self.frame_generator is None:
            return
            
        try:
            self.current_frame = next(self.frame_generator)
            self.frame_changed.emit(self.current_frame)
            self.current_frame_index_changed.emit(self.current_frame_index)
        except StopIteration:
            if self.is_playing:
                self.is_playing = False
                self.playback_state_changed.emit(False)
            self.reset_to_start()
    
    def reset_to_start(self):
        """Reset to the first frame"""
        if self.container is None:
            return
            
        self.current_frame_index = 0
        self.container.seek(self.first_frame_pts)
        self.frame_generator = self.container.decode(video=0)
        self._load_frame()
    
    def seek(self, frame_index):
        """Seek to a specific frame index"""
        if self.container is None or self.first_frame_pts is None:
            return
            
        # Ensure frame_index is within bounds
        frame_index = max(0, min(frame_index, self.frame_count - 1))

        print(f"Seeking to frame {frame_index}")
            
        # Calculate target PTS
        target_pts = self.first_frame_pts + (frame_index * self.frame_duration)
        
        # Seek to the nearest keyframe before our target
        self.container.seek(target_pts, stream=self.stream, backward=True)
        
        # Scan forward to find the exact frame we want
        self.frame_generator = self.container.decode(video=0)
        found_frame = False
        while not found_frame:
            try:
                frame = next(self.frame_generator)
                if frame.pts >= target_pts:
                    self.current_frame = frame
                    found_frame = True
            except StopIteration:
                break
        
        if found_frame:
            self.current_frame_index = frame_index
            self.frame_changed.emit(self.current_frame)
            self.current_frame_index_changed.emit(self.current_frame_index)
        else:
            # If we couldn't find the frame, reset to start
            self.reset_to_start()
    
    def advance_frame(self):
        """Advance to the next frame"""
        if self.container is None:
            return
            
        self.current_frame_index += 1
        if self.current_frame_index >= self.frame_count:
            if self.is_playing:
                self.is_playing = False
                self.playback_state_changed.emit(False)
            self.reset_to_start()
        else:
            self._load_frame()
    
    def toggle_playback(self):
        """Toggle between play and pause states"""
        self.is_playing = not self.is_playing
        self.playback_state_changed.emit(self.is_playing)
        return self.is_playing
    
    def get_frame_rate(self):
        """Get the video's frame rate"""
        return self.stream.average_rate if self.stream else 0
    
    def cleanup(self):
        """Clean up resources"""
        if self.container:
            self.container.close()
            self.container = None
            self.stream = None
            self.current_frame = None
            self.frame_generator = None
            self.first_frame_pts = None
            self.frame_duration = None
            self.frame_count = 0
            self.current_frame_index = 0
            self.is_playing = False
            self.video_id = None
            self.video_name = None
        
        # Close database connection
        if self.db:
            self.db.close() 