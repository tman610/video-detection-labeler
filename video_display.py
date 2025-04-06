from PySide6.QtWidgets import QGraphicsView, QGraphicsScene
from PySide6.QtCore import Qt, QRectF, Signal, QPoint
from PySide6.QtGui import QImage, QPixmap, QPainter

class VideoDisplay(QGraphicsView):
    """A QGraphicsView-based widget for displaying video frames"""
    
    # Signal to emit cursor position
    cursor_position_changed = Signal(int, int)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Set up the scene
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        
        # Set up the view
        self.setRenderHint(QPainter.Antialiasing)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        
        # Enable mouse tracking
        self.setMouseTracking(True)
        
        # Initialize variables
        self.current_image = None
        self.image_item = None
        self.zoom_factor = 1.0
        
        # Set up the background
        self.setBackgroundBrush(Qt.black)
    
    def display_frame(self, frame):
        """Display a frame in the view"""
        if frame is None:
            return
            
        # Convert the frame to QImage if it's not already
        if hasattr(frame, 'to_ndarray'):
            # Handle av.video.frame.VideoFrame objects
            frame_array = frame.to_ndarray(format='rgb24')
            height, width, channel = frame_array.shape
            bytes_per_line = 3 * width
            image = QImage(frame_array.data, width, height, bytes_per_line, QImage.Format_RGB888)
        elif isinstance(frame, QImage):
            # Frame is already a QImage
            image = frame
        else:
            # Assume frame is a numpy array with shape (height, width, 3)
            height, width, channel = frame.shape
            bytes_per_line = 3 * width
            image = QImage(frame.data, width, height, bytes_per_line, QImage.Format_RGB888)
        
        # Convert QImage to QPixmap
        pixmap = QPixmap.fromImage(image)
        
        # Store current transform and zoom factor
        current_transform = self.transform()
        current_zoom = self.zoom_factor
        
        # Clear the scene
        self.scene.clear()
        
        # Add the image to the scene
        self.image_item = self.scene.addPixmap(pixmap)
        self.current_image = pixmap
        
        # Set the scene rect to the image size
        self.scene.setSceneRect(self.image_item.boundingRect())
        
        # If this is the first frame, fit the view
        if current_zoom == 1.0:
            self.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)
        else:
            # Restore the previous transform
            self.setTransform(current_transform)
            self.zoom_factor = current_zoom
    
    def wheelEvent(self, event):
        """Handle mouse wheel events for zooming"""
        # Get the current scale factor
        old_pos = self.mapToScene(event.position().toPoint())
        
        # Calculate zoom factor
        zoom_in_factor = 1.15
        zoom_out_factor = 1 / zoom_in_factor
        
        # Apply zoom
        if event.angleDelta().y() > 0:
            # Zoom in
            self.scale(zoom_in_factor, zoom_in_factor)
            self.zoom_factor *= zoom_in_factor
        else:
            # Zoom out, but don't go below original size
            if self.zoom_factor * zoom_out_factor >= 1.0:
                self.scale(zoom_out_factor, zoom_out_factor)
                self.zoom_factor *= zoom_out_factor
            else:
                # Reset to original size
                self.resetTransform()
                self.zoom_factor = 1.0
                self.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)
        
        # Get the new position and adjust the view to keep the mouse position fixed
        new_pos = self.mapToScene(event.position().toPoint())
        delta = new_pos - old_pos
        self.translate(delta.x(), delta.y())
    
    def resizeEvent(self, event):
        """Handle resize events to maintain aspect ratio"""
        super().resizeEvent(event)
        
        # If there's an image, fit it to the view
        if self.image_item:
            self.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)
    
    def mouseMoveEvent(self, event):
        """Handle mouse move events to track cursor position"""
        super().mouseMoveEvent(event)
        
        # Get the position in scene coordinates
        scene_pos = self.mapToScene(event.pos())
        
        # Convert to image coordinates
        if self.image_item:
            # Get the image rect
            image_rect = self.image_item.boundingRect()
            
            # Check if the cursor is within the image bounds
            if image_rect.contains(scene_pos):
                # Calculate the position relative to the image
                x = int(scene_pos.x() - image_rect.left())
                y = int(scene_pos.y() - image_rect.top())
                
                # Emit the position
                self.cursor_position_changed.emit(x, y)
            else:
                # Cursor is outside the image
                self.cursor_position_changed.emit(-1, -1)
        else:
            # No image loaded
            self.cursor_position_changed.emit(-1, -1) 