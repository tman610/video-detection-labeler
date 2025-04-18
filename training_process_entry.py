import sys
import os
from multiprocessing import Process, Queue
from ultralytics import YOLO
import logging
import traceback
import builtins
import io

class QueueHandler(logging.Handler):
    """A logging handler that sends log records to a multiprocessing Queue."""
    def __init__(self, queue):
        super().__init__()
        self.queue = queue
        self.setFormatter(logging.Formatter('%(message)s'))  # Simplified format for cleaner output

    def emit(self, record):
        try:
            msg = self.format(record)
            self.queue.put(msg + '\n')
        except Exception:
            self.handleError(record)

class QueueLogStream:
    """A stream-like object that writes to a multiprocessing Queue."""
    def __init__(self, queue):
        self.queue = queue
        self.buffer = ''

    def write(self, text):
        if text:  # Send all text, not just lines
            self.queue.put(text)

    def flush(self):
        pass

    def isatty(self):
        return False

class PrintCapture:
    """Captures all print statements."""
    def __init__(self, queue):
        self.original_print = builtins.print
        self.queue = queue

    def custom_print(self, *args, **kwargs):
        # Capture the output that would have gone to print
        output = io.StringIO()
        kwargs['file'] = output
        self.original_print(*args, **kwargs)
        self.queue.put(output.getvalue())
        # Also send to original stdout for safety
        self.original_print(*args, **kwargs)

    def __enter__(self):
        builtins.print = self.custom_print

    def __exit__(self, exc_type, exc_val, exc_tb):
        builtins.print = self.original_print

def setup_logging(queue):
    """Set up logging capture for essential output only."""
    # 1. Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.WARNING)  # Only capture warnings and above
    
    # Remove any existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Add our queue handler
    queue_handler = QueueHandler(queue)
    root_logger.addHandler(queue_handler)
    
    # 2. Redirect stdout and stderr
    sys.stdout = QueueLogStream(queue)
    sys.stderr = QueueLogStream(queue)
    
    # 3. Configure specific loggers we care about
    loggers = [
        logging.getLogger('ultralytics'),  # Only capture ultralytics logs
        logging.getLogger()                # Root logger for our process
    ]
    
    for logger in loggers:
        logger.handlers = []  # Remove existing handlers
        logger.addHandler(queue_handler)
        logger.setLevel(logging.WARNING)  # Only capture warnings and above
        logger.propagate = True
    
    # Special case for ultralytics - we want to see its training progress
    ultralytics_logger = logging.getLogger('ultralytics')
    ultralytics_logger.setLevel(logging.INFO)  # Show training progress
    
    return queue_handler

def run_training_entry_point(data_yaml_path, project_name, log_queue):
    """Entry point for the training process."""
    try:
        # Set up comprehensive logging
        queue_handler = setup_logging(log_queue)
        
        # Capture print statements
        with PrintCapture(log_queue):
            # Log some initial information
            log_queue.put(f"Starting training process for project: {project_name}\n")
            log_queue.put(f"Using data file: {data_yaml_path}\n")
            
            # Initialize YOLO model
            model = YOLO('yolov8n.pt')
            
            # Start training
            model.train(
                data=data_yaml_path,
                project=os.path.join('runs', project_name),
                epochs=100,
                imgsz=640,
                batch=16,
                workers=4,
                device='0',  # Use GPU if available Ensure all output is shown
            )
            
            # Signal successful completion
            log_queue.put("TRAINING_COMPLETE\n")

    except Exception as e:
        # Send error information to the main process
        error_msg = f"Training failed: {str(e)}\n{traceback.format_exc()}"
        log_queue.put(f"TRAINING_ERROR: {error_msg}\n")
        sys.exit(1)
    finally:
        # Clean up logging
        if queue_handler and queue_handler in logging.getLogger().handlers:
            logging.getLogger().removeHandler(queue_handler)
        # Flush any remaining output
        sys.stdout.flush()
        sys.stderr.flush() 