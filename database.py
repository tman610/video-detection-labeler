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
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            fps REAL NOT NULL,
            frame_count INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS rectangles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id INTEGER NOT NULL,
            frame_index INTEGER NOT NULL,
            x1 INTEGER NOT NULL,
            y1 INTEGER NOT NULL,
            x2 INTEGER NOT NULL,
            y2 INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (video_id) REFERENCES videos (id),
            UNIQUE (video_id, frame_index, x1, y1, x2, y2)
        )
        ''')
        
        self.conn.commit()
    
    def get_video_by_name(self, name):
        """Get video information by name"""
        # Ensure name is a string
        name_str = str(name)
        self.cursor.execute("SELECT id, name, fps, frame_count FROM videos WHERE name = ?", (name_str,))
        return self.cursor.fetchone()
    
    def insert_video(self, name, fps, frame_count):
        """Insert a new video into the database"""
        try:
            # Ensure parameters are of the correct type
            name_str = str(name)
            fps_float = float(fps)
            frame_count_int = int(frame_count)
            
            self.cursor.execute(
                "INSERT INTO videos (name, fps, frame_count) VALUES (?, ?, ?)",
                (name_str, fps_float, frame_count_int)
            )
            self.conn.commit()
            return self.cursor.lastrowid
        except sqlite3.IntegrityError:
            # If the video already exists, get its ID
            self.cursor.execute("SELECT id FROM videos WHERE name = ?", (name_str,))
            result = self.cursor.fetchone()
            return result[0] if result else None
        except (ValueError, TypeError) as e:
            print(f"Error inserting video: {e}")
            return None
    
    def get_or_create_video(self, name, fps, frame_count):
        """Get video ID if it exists, otherwise create a new entry"""
        # Ensure name is a string
        name_str = str(name)
        
        # Check if video exists
        self.cursor.execute("SELECT id FROM videos WHERE name = ?", (name_str,))
        result = self.cursor.fetchone()
        
        if result:
            # Video exists, return its ID
            return result[0]
        else:
            # Video doesn't exist, insert it
            return self.insert_video(name_str, fps, frame_count)
    
    def save_rectangle(self, video_id, frame_index, x1, y1, x2, y2):
        """Save a rectangle to the database"""
        try:
            # Ensure parameters are of the correct type
            video_id_int = int(video_id)
            frame_index_int = int(frame_index)
            x1_int = int(x1)
            y1_int = int(y1)
            x2_int = int(x2)
            y2_int = int(y2)
            
            self.cursor.execute(
                "INSERT INTO rectangles (video_id, frame_index, x1, y1, x2, y2) VALUES (?, ?, ?, ?, ?, ?)",
                (video_id_int, frame_index_int, x1_int, y1_int, x2_int, y2_int)
            )
            self.conn.commit()
            return self.cursor.lastrowid
        except (ValueError, TypeError) as e:
            print(f"Error saving rectangle: {e}")
            return None
    
    
    def get_all_rectangles_for_video(self, video_id):
        """Get all rectangles for a video"""
        try:
            # Ensure video_id is of the correct type
            video_id = int(video_id)
            
            self.cursor.execute(
                """
                SELECT id, frame_index, x1, y1, x2, y2, created_at
                FROM rectangles
                WHERE video_id = ?
                ORDER BY frame_index
                """,
                (video_id,)
            )
            return self.cursor.fetchall()
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return []
    
    def close(self):
        """Close the database connection"""
        if self.conn:
            self.conn.close()
            self.conn = None
            self.cursor = None 