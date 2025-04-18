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
    rectangles_changed = Signal(list)  # Emits the list of rectangles for the current frame
    
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
        self.project_id = None  # Added project ID
        self.video_id = None
        self.video_name = None
        self.db = Database()
        
        # Dictionary to store rectangles for each frame
        self.rectangles = {}  # frame_index -> list of (class_id, x1, y1, x2, y2)
    
    def set_project(self, project_id):
        """Set the current project ID"""
        self.project_id = project_id
        # Potentially clear video/rectangles if project changes
        self.cleanup()
        print(f"Project set to: {self.project_id}")

    def load_video(self, file_path):
        """Load a video file and initialize the model for the current project"""
        if self.project_id is None:
            print("Error: Project not set. Please select a project first.")
            # Optionally emit an error signal or raise an exception
            return
            
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
            
            # Use the current project_id
            self.video_id = self.db.get_or_create_video(self.project_id, self.video_name, fps, frame_count)
            if self.video_id is None:
                raise Exception(f"Could not get or create video entry for {self.video_name} in project {self.project_id}")
            print(f"Video ID: {self.video_id} (Project: {self.project_id})")
            
            self.current_frame_index = 0
            self.frame_count_changed.emit(self.frame_count)
            self.fps_changed.emit(fps)
            
            # Clear and load rectangles from the database for this video
            self.rectangles = {}
            self._load_rectangles_from_db()
            
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
                
                # Emit rectangles for the first frame
                self._emit_rectangles_for_current_frame()
            except StopIteration:
                self.reset_to_start()
                
        except Exception as e:
            print(f"Error loading video: {e}")
            self.cleanup()
    
    def _load_rectangles_from_db(self):
        """Load rectangles (with class_id) from the database for the current video"""
        if self.video_id is None:
            return
            
        try:
            db_rectangles = self.db.get_all_rectangles_for_video(self.video_id)
            
            # Organize rectangles by frame index: {frame_idx: [(class_id, x1, y1, x2, y2), ...]}
            for rect in db_rectangles:
                frame_index = rect['frame_index']
                class_id = rect['class_id']
                x1, y1, x2, y2 = rect['x1'], rect['y1'], rect['x2'], rect['y2']
                
                if frame_index not in self.rectangles:
                    self.rectangles[frame_index] = []
                
                self.rectangles[frame_index].append((class_id, x1, y1, x2, y2))
            
            print(f"Loaded {len(db_rectangles)} rectangles from database for video {self.video_id}")
        except Exception as e:
            print(f"Error loading rectangles from database: {e}")
    
    def _load_frame(self):
        """Load the current frame and emit its rectangles"""
        if self.container is None or self.frame_generator is None:
            return
            
        try:
            self.current_frame = next(self.frame_generator)
            self.frame_changed.emit(self.current_frame)
            self.current_frame_index_changed.emit(self.current_frame_index)
            self._emit_rectangles_for_current_frame()
        except StopIteration:
            if self.is_playing:
                self.is_playing = False
                self.playback_state_changed.emit(False)
            self.reset_to_start()
    
    def _emit_rectangles_for_current_frame(self):
        """Emit rectangles (with class_id) for the current frame"""
        rects_data = self.rectangles.get(self.current_frame_index, [])
        self.rectangles_changed.emit(rects_data) # Emit list of (class_id, x1, y1, x2, y2)
    
    def add_rectangle(self, class_id, x1, y1, x2, y2):
        """Add a rectangle with a class ID to the current frame"""
        if self.video_id is None:
            print("Error: Cannot add rectangle, no video loaded.")
            return
        if class_id is None:
             print("Error: Cannot add rectangle, no class selected.")
             return

        # Create a new rectangle tuple
        rectangle_data = (class_id, x1, y1, x2, y2)
        
        frame_existed_before = self.current_frame_index in self.rectangles

        # Initialize the list for this frame if it doesn't exist
        if not frame_existed_before:
            self.rectangles[self.current_frame_index] = []
        
        # Add the rectangle to the in-memory list
        self.rectangles[self.current_frame_index].append(rectangle_data)
        
        # Save the rectangle to the database
        try:
            success = self.db.save_rectangle(
                self.video_id,
                self.current_frame_index,
                class_id,
                x1, y1, x2, y2
            )
            if success:
                print(f"Rectangle saved to DB: Video {self.video_id}, Frame {self.current_frame_index}, Class {class_id}")
            else:
                # If saving failed (e.g., duplicate), remove from memory list?
                # For now, we keep it in memory but log the issue.
                 print(f"Rectangle not saved to DB (likely duplicate): Video {self.video_id}, Frame {self.current_frame_index}, Class {class_id}")

        except Exception as e:
            print(f"Error saving rectangle to database: {e}")
        
        # Emit the updated rectangles for the current frame
        self._emit_rectangles_for_current_frame()
        
        # If this is the first rectangle for this frame, update the frame list
        if not frame_existed_before:
            # This could emit a signal, but for now, the controller will query
            pass 

        print(f"Rectangle added to frame {self.current_frame_index}: Class {class_id}, Coords ({x1},{y1})-({x2},{y2})")
    
    def get_frames_with_rectangles(self):
        """Return a sorted list of frame indices that have rectangles"""
        return sorted(list(self.rectangles.keys()))
    
    def get_frame_by_index(self, frame_index):
        """Retrieve and return a specific frame by index, returning the frame object (e.g., av.VideoFrame)"""
        if self.container is None or self.first_frame_pts is None or self.stream is None:
            print("Error: Cannot get frame, video not properly loaded.")
            return None
        if not (0 <= frame_index < self.frame_count):
            print(f"Error: Frame index {frame_index} out of bounds (0-{self.frame_count-1})")
            return None
            
        # Calculate target PTS
        target_pts = self.first_frame_pts + (frame_index * self.frame_duration)
        original_frame_index = self.current_frame_index # Store original position
        
        try:
            # Seek to the nearest keyframe before our target
            # Use 'any' direction for potentially faster seeking if needed, but backward is safer.
            self.container.seek(target_pts, stream=self.stream, backward=True) 
            
            # Decode frames until we find the exact one or pass it
            temp_frame_generator = self.container.decode(video=0)
            found_frame_obj = None
            while True:
                try:
                    frame = next(temp_frame_generator)
                    # Using pts is more reliable than assuming decoded order matches index directly after seek
                    if frame.pts >= target_pts: 
                        # Check if it's the *exact* frame or the first one after the target PTS
                        if frame.pts == target_pts or found_frame_obj is None:
                             found_frame_obj = frame
                        # If we already found a potential match and this one is later, break
                        if frame.pts > target_pts and found_frame_obj is not None: 
                           break 
                except StopIteration:
                    # Reached end of stream after seeking
                    break 
            
            if found_frame_obj:
                print(f"Retrieved frame for index {frame_index} (PTS: {found_frame_obj.pts})")
                return found_frame_obj
            else:
                print(f"Warning: Could not find exact frame for index {frame_index} after seeking.")
                return None

        except Exception as e:
            print(f"Error seeking/decoding frame {frame_index}: {e}")
            return None
        finally:
            # IMPORTANT: Seek back to the original position to not disrupt playback state
            # This is inefficient but necessary if we don't want get_frame_by_index to change the current frame
            if self.current_frame_index != original_frame_index:
                 print(f"Seeking back to original frame index {original_frame_index}")
                 self.seek(original_frame_index)
    
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
            
            # Emit rectangles for the current frame
            self._emit_rectangles_for_current_frame()
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
        # Don't reset project_id on cleanup unless intended
        # self.project_id = None 
        self.video_id = None
        self.video_name = None
        self.rectangles = {}  # Clear rectangles
        
        # Don't close DB connection here, manage it at application level
        # if self.db:
        #     self.db.close() 