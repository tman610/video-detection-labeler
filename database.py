import sqlite3
import os
import datetime

class Database:
    def __init__(self, db_path="videos.db"):
        """Initialize the database connection"""
        self.db_path = db_path
        self.conn = None
        self.cursor = None
        self._connect()
        self._create_tables()
    
    def _connect(self):
        """Connect to the SQLite database"""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
    
    def _create_tables(self):
        """Create necessary tables if they don't exist"""
        # Create projects table
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # Create classes table
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS classes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects (id),
            UNIQUE (project_id, name)
        )
        ''')

        # Create videos table (add project_id)
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            fps REAL NOT NULL,
            frame_count INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects (id),
            UNIQUE (project_id, name)
        )
        ''')
        
        # Create rectangles table (add class_id)
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS rectangles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id INTEGER NOT NULL,
            frame_index INTEGER NOT NULL,
            class_id INTEGER NOT NULL,
            x1 INTEGER NOT NULL,
            y1 INTEGER NOT NULL,
            x2 INTEGER NOT NULL,
            y2 INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (video_id) REFERENCES videos (id),
            FOREIGN KEY (class_id) REFERENCES classes (id),
            UNIQUE (video_id, frame_index, class_id, x1, y1, x2, y2)
        )
        ''')
        
        self.conn.commit()

    # --- Project Methods ---
    def create_project(self, name):
        """Create a new project"""
        try:
            self.cursor.execute("INSERT INTO projects (name) VALUES (?)", (str(name),))
            self.conn.commit()
            return self.cursor.lastrowid
        except sqlite3.IntegrityError:
            print(f"Project '{name}' already exists.")
            self.cursor.execute("SELECT id FROM projects WHERE name = ?", (str(name),))
            result = self.cursor.fetchone()
            return result[0] if result else None
        except sqlite3.Error as e:
            print(f"Database error creating project: {e}")
            return None

    def get_projects(self):
        """Get all projects"""
        try:
            self.cursor.execute("SELECT id, name FROM projects ORDER BY name")
            return self.cursor.fetchall()
        except sqlite3.Error as e:
            print(f"Database error getting projects: {e}")
            return []

    def get_project_name(self, project_id):
        """Get the name of a project by its ID"""
        try:
            self.cursor.execute("SELECT name FROM projects WHERE id = ?", (int(project_id),))
            result = self.cursor.fetchone()
            return result['name'] if result else None
        except sqlite3.Error as e:
            print(f"Database error getting project name: {e}")
            return None
        except (ValueError, TypeError) as e:
            print(f"Data type error getting project name: {e}")
            return None

    # --- Class Methods ---
    def create_class(self, project_id, name):
        """Create a new class for a project"""
        try:
            self.cursor.execute(
                "INSERT INTO classes (project_id, name) VALUES (?, ?)",
                (int(project_id), str(name))
            )
            self.conn.commit()
            return self.cursor.lastrowid
        except sqlite3.IntegrityError:
            print(f"Class '{name}' already exists for project {project_id}.")
            # Optionally return existing class ID if needed
            self.cursor.execute(
                "SELECT id FROM classes WHERE project_id = ? AND name = ?",
                (int(project_id), str(name))
            )
            result = self.cursor.fetchone()
            return result[0] if result else None
        except sqlite3.Error as e:
            print(f"Database error creating class: {e}")
            return None

    def get_classes_for_project(self, project_id):
        """Get all classes for a specific project"""
        try:
            self.cursor.execute(
                "SELECT id, name FROM classes WHERE project_id = ? ORDER BY name",
                (int(project_id),)
            )
            return self.cursor.fetchall()
        except sqlite3.Error as e:
            print(f"Database error getting classes: {e}")
            return []

    # --- Video Methods (Updated) ---
    def get_or_create_video(self, project_id, name, fps, frame_count):
        """Get a video by project and name, or create it if it doesn't exist"""
        try:
            project_id_int = int(project_id)
            name_str = str(name)
            fps_float = float(fps)
            frame_count_int = int(frame_count)

            # Try to get the video
            self.cursor.execute(
                "SELECT id FROM videos WHERE project_id = ? AND name = ?",
                (project_id_int, name_str)
            )
            result = self.cursor.fetchone()
            
            if result:
                # Video exists, return its ID
                return result[0]
            else:
                # Video doesn't exist, create it
                self.cursor.execute(
                    "INSERT INTO videos (project_id, name, fps, frame_count) VALUES (?, ?, ?, ?)",
                    (project_id_int, name_str, fps_float, frame_count_int)
                )
                self.conn.commit()
                return self.cursor.lastrowid
        except sqlite3.Error as e:
            print(f"Database error in get_or_create_video: {e}")
            return None
        except (ValueError, TypeError) as e:
            print(f"Data type error in get_or_create_video: {e}")
            return None

    def get_video_id(self, project_id, name):
        """Get a video ID by project and name"""
        try:
            self.cursor.execute(
                "SELECT id FROM videos WHERE project_id = ? AND name = ?",
                (int(project_id), str(name))
            )
            result = self.cursor.fetchone()
            return result[0] if result else None
        except sqlite3.Error as e:
            print(f"Database error getting video ID: {e}")
            return None

    # --- Rectangle Methods (Updated) ---
    def save_rectangle(self, video_id, frame_index, class_id, x1, y1, x2, y2):
        """Save a rectangle to the database"""
        try:
            # Ensure parameters are of the correct type
            video_id_int = int(video_id)
            frame_index_int = int(frame_index)
            class_id_int = int(class_id)
            x1_int = int(x1)
            y1_int = int(y1)
            x2_int = int(x2)
            y2_int = int(y2)
            
            # Try to insert the rectangle
            self.cursor.execute(
                """
                INSERT INTO rectangles (video_id, frame_index, class_id, x1, y1, x2, y2)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (video_id_int, frame_index_int, class_id_int, x1_int, y1_int, x2_int, y2_int)
            )
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            # Rectangle already exists (based on UNIQUE constraint)
            print(f"Rectangle already exists for video {video_id}, frame {frame_index}, class {class_id}")
            return False
        except sqlite3.Error as e:
            print(f"Database error saving rectangle: {e}")
            return False
        except (ValueError, TypeError) as e:
            print(f"Data type error saving rectangle: {e}")
            return False
    
    def get_rectangles_for_frame(self, video_id, frame_index):
        """Get all rectangles (with class_id) for a specific frame of a video"""
        try:
            video_id_int = int(video_id)
            frame_index_int = int(frame_index)
            
            self.cursor.execute(
                """
                SELECT id, video_id, frame_index, class_id, x1, y1, x2, y2, created_at
                FROM rectangles
                WHERE video_id = ? AND frame_index = ?
                """,
                (video_id_int, frame_index_int)
            )
            return self.cursor.fetchall()
        except sqlite3.Error as e:
            print(f"Database error getting rectangles for frame: {e}")
            return []
        except (ValueError, TypeError) as e:
            print(f"Data type error getting rectangles for frame: {e}")
            return []
    
    def get_all_rectangles_for_video(self, video_id):
        """Get all rectangles (with class_id) for a video"""
        try:
            video_id_int = int(video_id)
            
            self.cursor.execute(
                """
                SELECT id, frame_index, class_id, x1, y1, x2, y2, created_at
                FROM rectangles
                WHERE video_id = ?
                ORDER BY frame_index
                """,
                (video_id_int,)
            )
            return self.cursor.fetchall()
        except sqlite3.Error as e:
            print(f"Database error getting all rectangles for video: {e}")
            return []
        except (ValueError, TypeError) as e:
            print(f"Data type error getting all rectangles for video: {e}")
            return []
    
    def close(self):
        """Close the database connection"""
        if self.conn:
            self.conn.close()
            self.conn = None
            self.cursor = None 