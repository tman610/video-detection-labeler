import sqlite3
import os

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
    
    def close(self):
        """Close the database connection"""
        if self.conn:
            self.conn.close()
            self.conn = None
            self.cursor = None 