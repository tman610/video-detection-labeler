import sys
from PySide6.QtWidgets import QApplication
from video_model import VideoModel
from video_view import VideoView
from video_controller import VideoController

def main():
    # Create the application
    app = QApplication(sys.argv)
    
    # Create MVC components
    model = VideoModel()
    view = VideoView()
    controller = VideoController(model, view)
    
    # Show the view
    view.show()
    
    # Run the application
    exit_code = app.exec()
    
    # Clean up resources
    controller.cleanup()  # Clean up controller resources first
    model.cleanup()      # Then clean up model resources
    
    return exit_code

if __name__ == "__main__":
    sys.exit(main()) 