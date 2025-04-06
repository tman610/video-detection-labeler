from PySide6.QtWidgets import QGraphicsRectItem, QGraphicsView, QGraphicsScene, QGraphicsItem
from PySide6.QtCore import Qt, QRectF, Signal, QPoint
from PySide6.QtGui import QImage, QPixmap, QPainter, QPen, QColor, QBrush

class VideoDisplay(QGraphicsView):
    """A QGraphicsView-based widget for displaying video frames"""
    
    # Signal to emit cursor position
    cursor_position_changed = Signal(int, int)
    
    # Signal to emit when a rectangle is drawn
    rectangle_drawn = Signal(int, int, int, int)  # x1, y1, x2, y2
    
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
        
        # Rectangle drawing variables
        self.drawing_rectangle = False
        self.start_point = None
        self.current_rect = None
        self.rectangles = []  # List to store rectangles for current frame
        
        # Set up the background
        self.setBackgroundBrush(Qt.black)
        
        # Enable rubber band selection for zooming
        self.setDragMode(QGraphicsView.RubberBandDrag)
    
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
        
        # Redraw all rectangles
        self._draw_rectangles()
    
    def mousePressEvent(self, event):
        """Handle mouse press events for rectangle drawing"""
        if event.button() == Qt.LeftButton:
            # Get the position in scene coordinates
            scene_pos = self.mapToScene(event.pos())
            
            # Check if we're within the image bounds
            if self.image_item and self.image_item.boundingRect().contains(scene_pos):
                self.drawing_rectangle = True
                self.start_point = scene_pos
                self.current_rect = self.scene.addRect(
                    QRectF(self.start_point, self.start_point),
                    QPen(QColor(255, 0, 0), 2),
                    QBrush(Qt.NoBrush)
                )
                self.current_rect.setZValue(1)
        
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        """Handle mouse move events for rectangle drawing and cursor tracking"""
        super().mouseMoveEvent(event)
        
        # Get the position in scene coordinates
        scene_pos = self.mapToScene(event.pos())
        
        # Handle rectangle drawing
        if self.drawing_rectangle and self.current_rect:
            # Update the rectangle
            self.current_rect.setRect(QRectF(self.start_point, scene_pos))
        
        # Handle cursor position tracking
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
    
    def mouseReleaseEvent(self, event):
        """Handle mouse release events for rectangle drawing"""
        if event.button() == Qt.LeftButton and self.drawing_rectangle:
            # Get the end position in scene coordinates
            end_pos = self.mapToScene(event.pos())
            
            # Get the image rect
            image_rect = self.image_item.boundingRect()
            
            # Check if both points are within the image bounds
            if (image_rect.contains(self.start_point) and 
                image_rect.contains(end_pos)):
                
                # Calculate the rectangle coordinates relative to the image
                x1 = int(min(self.start_point.x(), end_pos.x()) - image_rect.left())
                y1 = int(min(self.start_point.y(), end_pos.y()) - image_rect.top())
                x2 = int(max(self.start_point.x(), end_pos.x()) - image_rect.left())
                y2 = int(max(self.start_point.y(), end_pos.y()) - image_rect.top())
                
                # Print the rectangle coordinates (for debugging)
                print(f"Rectangle drawn: ({x1}, {y1}) to ({x2}, {y2})")
                
                # Emit the rectangle coordinates
                self.rectangle_drawn.emit(x1, y1, x2, y2)
            
            # Clean up
            self.drawing_rectangle = False
            self.start_point = None
            self.current_rect = None
    
    def wheelEvent(self, event):
        """Handle mouse wheel events for zooming"""
        # Get the current scale factor
        old_pos = self.mapToScene(event.position().toPoint())
        
        # Calculate zoom factor
        zoom_in_factor = 1.25
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
    
    def set_rectangles(self, rectangles):
        """Set the rectangles to display for the current frame"""
        self.rectangles = rectangles
        self._draw_rectangles()
    
    def _draw_rectangles(self):
        """Draw all rectangles for the current frame"""
        # Remove existing rectangles
        for item in self.scene.items():
            if isinstance(item, QGraphicsRectItem):
                self.scene.removeItem(item)
                
        # Draw new rectangles
        for rect in self.rectangles:
            x1, y1, x2, y2 = rect
            self.scene.addRect(
                QRectF(x1, y1, x2 - x1, y2 - y1),
                QPen(QColor(255, 0, 0), 2),
                QBrush(Qt.NoBrush)
            ).setZValue(1) 