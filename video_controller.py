from PySide6.QtCore import QTimer, Qt
import time

class VideoController:
    def __init__(self, model, view):
        self.model = model
        self.view = view
        self.timer = QTimer()
        self.timer.timeout.connect(self._on_timer_timeout)
        self.last_frame_time = 0
        
        # --- Connect View Signals ---
        # Project/Class signals
        self.view.project_dropdown.currentIndexChanged.connect(self._on_project_selected)
        self.view.add_project_button.clicked.connect(self._add_project)
        self.view.add_current_class_button.clicked.connect(self._add_class)
        # Open video button (now project-aware)
        self.view.open_button.clicked.connect(self.open_video)
        
        # Labeled Frames List
        self.view.labeled_frames_list.itemClicked.connect(self._on_frame_list_item_clicked)
        # New List Navigation Signals
        self.view.navigate_labeled_up.connect(self._navigate_labeled_list_up)
        self.view.navigate_labeled_down.connect(self._navigate_labeled_list_down)
        
        # Video control signals
        self.view.play_button.clicked.connect(self.toggle_playback)
        self.view.prev_frame.clicked.connect(lambda: self.model.seek(self.model.current_frame_index - 1))
        self.view.next_frame.clicked.connect(self.model.advance_frame)
        # Connect +/- 10 frame buttons
        self.view.prev_10_frames.clicked.connect(lambda: self.model.seek(self.model.current_frame_index - 10))
        self.view.next_10_frames.clicked.connect(lambda: self.model.seek(self.model.current_frame_index + 10))
        self.view.seek_slider.sliderMoved.connect(self._on_slider_moved)
        self.view.seek_slider.sliderReleased.connect(self._on_slider_released)
        self.view.speed_dropdown.currentIndexChanged.connect(self._on_speed_changed)
        
        # Rectangle drawing signal
        self.view.video_display.rectangle_drawn.connect(self._on_rectangle_drawn)

        # --- Connect Model Signals ---
        self.model.frame_changed.connect(self.view.display_frame)
        self.model.frame_count_changed.connect(self._on_frame_count_changed)
        self.model.current_frame_index_changed.connect(self._on_current_frame_changed)
        self.model.playback_state_changed.connect(self._on_playback_state_changed)
        self.model.fps_changed.connect(self.view.update_fps)
        self.model.rectangles_changed.connect(self._on_rectangles_changed) # Updated connection

        # --- Initial Population ---
        self._populate_projects()
    
    # --- Project and Class Handling ---
    def _populate_projects(self):
        """Load projects from DB and populate dropdown"""
        projects = self.model.db.get_projects()
        self.view.populate_project_dropdown(projects)
        # Automatically select the first project if available
        if projects:
            self._on_project_selected(0) # Trigger selection logic for the first item
        else:
            self.view.populate_class_list([]) # Clear class list if no project
            self.view.populate_current_class_dropdown([]) # Clear class dropdown
            self.view.clear_labeled_frames_list() # Clear frames list

    def _add_project(self):
        """Handle Add Project button click"""
        name = self.view.get_new_project_name()
        if name:
            project_id = self.model.db.create_project(name)
            if project_id:
                print(f"Project '{name}' created with ID: {project_id}")
                self._populate_projects()
                # Select the newly added project
                self.view.set_selected_project(project_id)
            else:
                self.view.show_error_message("Error", f"Failed to create project '{name}'.")

    def _on_project_selected(self, index):
        """Handle project selection change"""
        project_id = self.view.get_selected_project_id()
        if project_id is not None and project_id != -1:
            print(f"Project selected: ID {project_id}")
            self.model.set_project(project_id) # Inform the model
            self._populate_classes_for_project(project_id)
            self.view.clear_labeled_frames_list() # Clear frames list when project changes
        else:
            # Handle case where "No projects found" is selected or no project ID
            self.model.set_project(None)
            self.view.populate_class_list([])
            self.view.populate_current_class_dropdown([])
            self.view.clear_labeled_frames_list() # Clear frames list

    def _populate_classes_for_project(self, project_id):
        """Load classes for the selected project and update UI"""
        classes = self.model.db.get_classes_for_project(project_id)
        self.view.populate_current_class_dropdown(classes)

    def _add_class(self):
        """Handle Add Class button click"""
        project_id = self.view.get_selected_project_id()
        if project_id is None or project_id == -1:
            self.view.show_error_message("Error", "Please select a project first.")
            return

        name = self.view.get_new_class_name()
        if name:
            class_id = self.model.db.create_class(project_id, name)
            if class_id:
                print(f"Class '{name}' created for project {project_id} with ID: {class_id}")
                # Repopulate class lists
                self._populate_classes_for_project(project_id)
            else:
                 self.view.show_error_message("Error", f"Failed to create class '{name}'. It might already exist.")

    # --- Video Handling ---
    def open_video(self):
        """Handle opening a new video file for the selected project"""
        project_id = self.view.get_selected_project_id()
        if project_id is None or project_id == -1:
            self.view.show_error_message("Error", "Please select a project before opening a video.")
            return

        file_path = self.view.get_open_file_path()
        if file_path:
            # Model's load_video now implicitly uses the project_id set via set_project
            self.model.load_video(file_path)
            # Populate the labeled frames list after loading video
            self._update_labeled_frames_list()
    
    # --- Labeled Frames List Handling ---
    def _update_labeled_frames_list(self):
        """Update the list of frames containing rectangles"""
        if self.model.video_id is not None:
            frame_numbers = self.model.get_frames_with_rectangles()
            self.view.populate_labeled_frames_list(frame_numbers)
        else:
            self.view.clear_labeled_frames_list()

    def _on_frame_list_item_clicked(self, item):
        """Handle clicks on the labeled frames list"""
        print("_on_frame_list_item_clicked triggered!") # DEBUG
        try:
            frame_number = item.data(Qt.UserRole) # Get frame number from item data
            print(f"  Item data (frame number): {frame_number} (Type: {type(frame_number)})") # DEBUG
            
            if frame_number is not None and self.model.video_id is not None:
                print(f"  Seeking to frame {frame_number}...") # DEBUG
                self.model.seek(frame_number)
                print(f"  Seek called for frame {frame_number}.") # DEBUG
            else:
                print(f"  Seek not called. Frame number: {frame_number}, Video ID: {self.model.video_id}") # DEBUG
        except Exception as e:
            print(f"  Error in _on_frame_list_item_clicked: {e}") # DEBUG

    def _navigate_labeled_list(self, direction):
        """Navigate the labeled list up or down and seek to the selected frame."""
        count = self.view.get_labeled_frame_count()
        if count == 0 or self.model.video_id is None:
            return # Nothing to navigate
            
        current_index = self.view.get_current_labeled_frame_index()
        
        if direction == "up":
            next_index = current_index - 1
            if next_index < 0:
                next_index = count - 1 # Wrap around to the bottom
        elif direction == "down":
            next_index = current_index + 1
            if next_index >= count:
                next_index = 0 # Wrap around to the top
        else:
            return # Invalid direction

        # Select the new item in the view
        new_item = self.view.select_labeled_frame_item(next_index)
        
        # Seek to the frame corresponding to the new item
        if new_item:
            self._on_frame_list_item_clicked(new_item) # Reuse click logic to seek

    def _navigate_labeled_list_up(self):
        self._navigate_labeled_list("up")

    def _navigate_labeled_list_down(self):
        self._navigate_labeled_list("down")

    # --- Playback and Navigation (Mostly Unchanged) ---
    def toggle_playback(self):
        """Handle play/pause button click"""
        # Check if a video is loaded
        if self.model.video_id is None:
             self.view.show_error_message("Info", "Please open a video first.")
             return 
        is_playing = self.model.toggle_playback()
        if is_playing:
            self._start_playback_timer()
        else:
            self.timer.stop()
    
    def _start_playback_timer(self):
        """Start the playback timer with the current speed"""
        frame_rate = self.model.get_frame_rate()
        if frame_rate > 0:
            speed = self.view.get_speed_multiplier()
            interval = int(1000 / (frame_rate * speed))
            self.timer.start(interval)
            self.last_frame_time = time.time()
    
    def _on_speed_changed(self, index):
        """Handle speed dropdown changes"""
        if self.model.is_playing:
            self._start_playback_timer()
    
    def _on_timer_timeout(self):
        """Handle timer timeout for frame advancement"""
        # Check if a video is loaded and playing
        if self.model.video_id is None or not self.model.is_playing:
            self.timer.stop()
            return
            
        current_time = time.time()
        speed = self.view.get_speed_multiplier()
        try:
            frame_rate = self.model.get_frame_rate()
            if frame_rate <= 0:
                 self.timer.stop()
                 return
            frame_duration = 1.0 / (frame_rate * speed)
        except ZeroDivisionError:
            self.timer.stop() # Stop timer if frame rate is invalid
            return
        
        # Check if it's time for the next frame
        if current_time - self.last_frame_time >= frame_duration:
            self.model.advance_frame()
            self.last_frame_time = current_time
    
    def _on_frame_count_changed(self, frame_count):
        """Handle frame count changes"""
        self.view.update_seek_slider(0, frame_count)
    
    def _on_current_frame_changed(self, frame_index):
        """Handle current frame index changes"""
        self.view.update_frame_counter(frame_index, self.model.frame_count)
        self.view.update_seek_slider(frame_index, self.model.frame_count)
    
    def _on_playback_state_changed(self, is_playing):
        """Handle playback state changes"""
        self.view.update_play_button(is_playing)
        if not is_playing:
            self.timer.stop()
    
    def _on_slider_moved(self, value):
        """Handle slider movement (dragging)"""
        if self.model.video_id is not None:
            self.model.seek(value)
    
    def _on_slider_released(self):
        """Handle slider release (clicking)"""
        if self.model.video_id is not None:
            value = self.view.seek_slider.value()
            self.model.seek(value)
        
    # --- Rectangle Handling ---
    def _on_rectangle_drawn(self, x1, y1, x2, y2):
        """Handle rectangle drawn signal from the view"""
        class_id = self.view.get_selected_class_id()
        if class_id is None or class_id == -1:
             self.view.show_error_message("Error", "Please select a class before drawing a rectangle.")
             # Remove the temporary rectangle drawn by the view if needed
             # self.view.video_display.clear_current_drawing_rect()
             return
        if self.model.video_id is None:
            self.view.show_error_message("Error", "Please open a video first.")
            # self.view.video_display.clear_current_drawing_rect()
            return
            
        # Add the rectangle to the model (which also saves to DB)
        self.model.add_rectangle(class_id, x1, y1, x2, y2)
        # Update the list of labeled frames potentially
        self._update_labeled_frames_list() 

    def _on_rectangles_changed(self, rectangles_data):
         """Handle the signal from the model when rectangles for the current frame change."""
         # rectangles_data is a list of tuples: [(class_id, x1, y1, x2, y2), ...]
         # We need to potentially map class_id back to class name or color for display if needed.
         # For now, just pass the geometric data to set_rectangles.
         # TODO: Enhance VideoDisplay to handle class information (e.g., different colors)
         rects_for_display = [(r[1], r[2], r[3], r[4]) for r in rectangles_data]
         self.view.video_display.set_rectangles(rects_for_display)
         # Update the labeled frames list as rectangles might have changed
         # Optimization: Could check if the *set* of labeled frames actually changed
         # self._update_labeled_frames_list() # This is called after add_rectangle now 
