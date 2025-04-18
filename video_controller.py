from PySide6.QtCore import QTimer, Qt, QObject, Signal
import time
import os
import random
from collections import defaultdict
from PIL import Image
import yaml
import threading
from ultralytics import YOLO
from ultralytics import settings
import traceback
import io
import logging
import contextlib
import sys
from multiprocessing import Process, Queue
from training_process_entry import run_training_entry_point

# --- Helper Class to Redirect Stdout/Stderr --- 
class GUILogStream(QObject):
    text_written = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        # You might add buffering here if needed, but keep it simple first

    def write(self, text):
        # This method is called by print() or sys.stdout.write()
        # Emit the signal to send the text to the main thread
        self.text_written.emit(text)
        return len(text) # write must return the number of bytes written

    def flush(self):
        # No-op needed for IOBase compatibility (though not strictly required now)
        pass

    # Add other methods needed to mimic a stream if libraries check for them
    # (e.g., isatty() often needed)
    def isatty(self):
        return False

# --- Video Controller --- 
class VideoController:
    def __init__(self, model, view):
        self.model = model
        self.view = view
        self.timer = QTimer()
        self.timer.timeout.connect(self._on_timer_timeout)
        self.last_frame_time = 0
        self.is_training = False # Flag to track training state
        self.log_stream = None # Placeholder for the stream instance
        self.training_process = None
        self.log_queue = None
        self.log_timer = QTimer()
        self.log_timer.timeout.connect(self._process_log_queue)
        
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
        
        # Export Button
        self.view.export_button.clicked.connect(self._export_dataset)
        # Train Button
        self.view.train_button.clicked.connect(self._start_training)
        # Stop Button (now from log dialog)
        self.view.training_log_dialog.stop_button.clicked.connect(self.stop_training)

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
        try:
            frame_number = item.data(Qt.UserRole) # Get frame number from item data
            
            if frame_number is not None and self.model.video_id is not None:
                self.model.seek(frame_number)
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
             return
        if self.model.video_id is None:
            self.view.show_error_message("Error", "Please open a video first.")
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

    # --- Export --- 
    def _export_dataset(self):
        """Exports labeled frames and YOLO annotations for the current video."""
        project_id = self.view.get_selected_project_id()
        video_id = self.model.video_id
        video_name = self.model.video_name

        # --- Initial Checks --- 
        if project_id is None or project_id == -1:
            self.view.show_error_message("Export Error", "Please select a project.")
            return
        if video_id is None:
            self.view.show_error_message("Export Error", "Please open a video.")
            return

        project_name = self.model.db.get_project_name(project_id)
        if not project_name:
             self.view.show_error_message("Export Error", f"Could not find project name for ID {project_id}.")
             return
             
        print(f"Starting export for Project: '{project_name}', Video: '{video_name}'")

        # --- Get Class Info --- 
        classes = self.model.db.get_classes_for_project(project_id)
        if not classes:
            self.view.show_error_message("Export Error", "No classes defined for this project.")
            return
        # Create map: DB class_id -> 0-based yolo_index
        class_id_to_yolo_index = {row['id']: index for index, row in enumerate(classes)}
        # Create ordered list of class names for YAML
        class_names_ordered = [row['name'] for row in classes] # Ensure order matches yolo index
        print(f"  Class mapping: {class_id_to_yolo_index}")
        print(f"  Class names: {class_names_ordered}")

        # --- Get Rectangle Data --- 
        all_rectangles = self.model.db.get_all_rectangles_for_video(video_id)
        if not all_rectangles:
            self.view.show_error_message("Export Error", "No rectangles found for this video.")
            return
            
        rects_by_frame = defaultdict(list)
        for rect in all_rectangles:
            rects_by_frame[rect['frame_index']].append(rect)
            
        labeled_frame_indices = sorted(list(rects_by_frame.keys()))
        print(f"  Found {len(labeled_frame_indices)} frames with labels.")

        # --- Prepare Directories --- 
        base_export_dir = os.path.abspath(os.path.join("datasets", project_name))
        train_img_dir = os.path.join(base_export_dir, "train", "images")
        train_lbl_dir = os.path.join(base_export_dir, "train", "labels")
        valid_img_dir = os.path.join(base_export_dir, "valid", "images")
        valid_lbl_dir = os.path.join(base_export_dir, "valid", "labels")

        try:
            os.makedirs(train_img_dir, exist_ok=True)
            os.makedirs(train_lbl_dir, exist_ok=True)
            os.makedirs(valid_img_dir, exist_ok=True)
            os.makedirs(valid_lbl_dir, exist_ok=True)
            print(f"  Created directories under '{base_export_dir}'")
        except OSError as e:
             self.view.show_error_message("Export Error", f"Failed to create directories: {e}")
             return

        # --- Create data.yaml (Using Absolute Path Base + Relative Train/Val) --- 
        yaml_path = os.path.join(base_export_dir, "data.yaml")
        # Define paths relative to the base_export_dir
        train_rel_path = os.path.join('train', 'images') 
        val_rel_path = os.path.join('valid', 'images')
        yaml_data = {
            'path': base_export_dir.replace(os.sep, '/'), # Absolute path to dataset root (use forward slashes)
            'train': train_rel_path.replace(os.sep, '/'), # Path relative to 'path'
            'val': val_rel_path.replace(os.sep, '/'),   # Path relative to 'path'
            'nc': len(class_names_ordered),
            'names': class_names_ordered,
            'tool-source': {
                'name': 'tman610',
                'url': 'https://github.com/tman610'
            }
        }
        try:
            print(f"  Attempting to write data.yaml to: {yaml_path}") # DEBUG
            print(f"  YAML content: {yaml_data}") # DEBUG
            with open(yaml_path, 'w') as f:
                yaml.dump(yaml_data, f, default_flow_style=False, sort_keys=False)
            print(f"  Successfully created data.yaml") # DEBUG
        except Exception as e:
            print(f"  ERROR writing data.yaml: {e}") # DEBUG
            self.view.show_error_message("Export Warning", f"Failed to write data.yaml: {e}")
            # Continue export even if YAML fails for now
        
        # --- Split Data --- 
        random.shuffle(labeled_frame_indices)
        split_index = int(len(labeled_frame_indices) * 0.8)
        train_indices = labeled_frame_indices[:split_index]
        valid_indices = labeled_frame_indices[split_index:]
        print(f"  Splitting into {len(train_indices)} train, {len(valid_indices)} valid frames.")

        # --- Process and Save Frames/Labels --- 
        export_count = 0
        error_count = 0
        video_name_base = os.path.splitext(video_name)[0]

        for frame_index in train_indices + valid_indices:
            is_train = frame_index in train_indices
            img_dir = train_img_dir if is_train else valid_img_dir
            lbl_dir = train_lbl_dir if is_train else valid_lbl_dir
            
            av_frame = self.model.get_frame_by_index(frame_index)
            if av_frame is None:
                print(f"  ERROR: Could not retrieve frame {frame_index}. Skipping.")
                error_count += 1
                continue

            try:
                pil_image = av_frame.to_image()
                img_width, img_height = pil_image.size
                if img_width <= 0 or img_height <= 0:
                    print(f"  ERROR: Invalid dimensions for frame {frame_index} ({img_width}x{img_height}). Skipping.")
                    error_count += 1
                    continue

                img_filename = f"{video_name_base}_frame_{frame_index}.bmp"
                img_path = os.path.join(img_dir, img_filename)
                pil_image.save(img_path, "BMP")

                yolo_lines = []
                rectangles_for_this_frame = rects_by_frame[frame_index]
                for rect in rectangles_for_this_frame:
                    class_id = rect['class_id']
                    x1, y1, x2, y2 = rect['x1'], rect['y1'], rect['x2'], rect['y2']
                    
                    if class_id not in class_id_to_yolo_index:
                        print(f"  WARNING: Class ID {class_id} not found in project map for frame {frame_index}. Skipping this box.")
                        continue
                    yolo_class_index = class_id_to_yolo_index[class_id]
                    
                    box_width = x2 - x1
                    box_height = y2 - y1
                    center_x = x1 + box_width / 2
                    center_y = y1 + box_height / 2
                    
                    norm_center_x = center_x / img_width
                    norm_center_y = center_y / img_height
                    norm_width = box_width / img_width
                    norm_height = box_height / img_height
                    
                    norm_center_x = max(0.0, min(1.0, norm_center_x))
                    norm_center_y = max(0.0, min(1.0, norm_center_y))
                    norm_width = max(0.0, min(1.0, norm_width))
                    norm_height = max(0.0, min(1.0, norm_height))

                    yolo_lines.append(f"{yolo_class_index} {norm_center_x:.6f} {norm_center_y:.6f} {norm_width:.6f} {norm_height:.6f}")
                
                lbl_filename = f"{video_name_base}_frame_{frame_index}.txt"
                lbl_path = os.path.join(lbl_dir, lbl_filename)
                with open(lbl_path, 'w') as f:
                    f.write("\n".join(yolo_lines))
                
                export_count += 1
            except Exception as e:
                print(f"  ERROR processing frame {frame_index}: {e}")
                error_count += 1
        
        # --- Report Results --- 
        message = f"Export complete for '{video_name}'.\n"
        message += f"  Total labeled frames: {len(labeled_frame_indices)}\n"
        message += f"  Successfully exported: {export_count}\n"
        if error_count > 0:
             message += f"  Errors encountered: {error_count}\n"
        message += f"Dataset saved in: '{base_export_dir}'"
        
        print(message)
        self.view.show_info_message("Export Finished", message)

    # --- Training --- 
    def _start_training(self):
        """Start the training process in a separate process."""
        if self.is_training:
            self.view.show_info_message("Training Info", "Training is already in progress.")
            return

        project_id = self.view.get_selected_project_id()
        if project_id is None or project_id == -1:
            self.view.show_error_message("Training Error", "Please select a project first.")
            return
            
        project_name = self.model.db.get_project_name(project_id)
        if not project_name:
            self.view.show_error_message("Training Error", f"Could not find project name for ID {project_id}.")
            return
            
        data_yaml_path = os.path.abspath(os.path.join('datasets', project_name, 'data.yaml'))
        if not os.path.exists(data_yaml_path):
            self.view.show_error_message(
                "Training Error", 
                f"Dataset file not found:\n{data_yaml_path}\n\nPlease export the dataset first."
            )
            return

        # Prepare and show the log dialog
        self.view.clear_log_dialog()
        self.view.show_log_dialog()
        self.view.training_log_dialog.stop_button.setEnabled(True)  # Enable stop button

        # Create a queue for log messages
        self.log_queue = Queue()
        
        # Start the training process
        self.training_process = Process(
            target=run_training_entry_point,
            args=(data_yaml_path, project_name, self.log_queue)
        )
        self.training_process.start()
        
        # Start the log processing timer
        self.log_timer.start(100)  # Check queue every 100ms
        
        # Update UI state
        self.is_training = True
        self.view.train_button.setEnabled(False)
        self.view.train_button.setText("Training...")

    def _process_log_queue(self):
        """Process log messages from the training process."""
        if not self.log_queue:
            return

        while not self.log_queue.empty():
            try:
                message = self.log_queue.get_nowait()
                
                if message.startswith("TRAINING_COMPLETE"):
                    self._training_finished(True, "Training completed successfully")
                elif message.startswith("TRAINING_ERROR:"):
                    error_msg = message[len("TRAINING_ERROR:"):]
                    self._training_finished(False, error_msg)
                else:
                    self.view.append_log_text(message)
            except Exception as e:
                print(f"Error processing log message: {e}")

    def _training_finished(self, success, message):
        """Handle training completion."""
        self.is_training = False
        self.view.train_button.setEnabled(True)
        self.view.train_button.setText("Train Model")
        self.view.training_log_dialog.stop_button.setEnabled(False)  # Disable stop button
        
        if self.training_process:
            if self.training_process.is_alive():
                self.training_process.terminate()
                try:
                    self.training_process.join(timeout=5.0)  # Wait up to 5 seconds for process to terminate
                except Exception:
                    pass  # Ignore any errors during join
            self.training_process = None
        
        if self.log_queue:
            self.log_queue.close()
            self.log_queue = None
        
        self.log_timer.stop()
        
        if success:
            self.view.show_info_message("Training Finished", message)
        else:
            self.view.show_error_message("Training Failed", message)

    def stop_training(self):
        """Stop the training process."""
        if self.is_training and self.training_process:
            self.training_process.terminate()
            self._training_finished(False, "Training stopped by user")

    def cleanup(self):
        """Clean up resources when the application is closing."""
        if self.is_training and self.training_process:
            self.training_process.terminate()
            try:
                self.training_process.join(timeout=5.0)  # Wait up to 5 seconds for process to terminate
            except Exception:
                pass  # Ignore any errors during join
            self.training_process = None
        
        if self.log_queue:
            self.log_queue.close()
            self.log_queue = None
        
        self.log_timer.stop()
        
        # Ensure log dialog is closed and logging is restored
        if hasattr(self.view, 'training_log_dialog'):
            self.view.training_log_dialog.close()
