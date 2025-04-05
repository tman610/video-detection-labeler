import sys
from PySide6.QtWidgets import QApplication
from video_model import VideoModel
from video_view import VideoView
from video_controller import VideoController

def main():
    app = QApplication(sys.argv)
    
    # Create MVC components
    model = VideoModel()
    view = VideoView()
    controller = VideoController(model, view)
    
    # Show the view
    view.show()
    
    # Start the application
    sys.exit(app.exec())

if __name__ == "__main__":
    main() 