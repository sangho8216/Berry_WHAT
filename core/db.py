import sqlite3
from datetime import datetime

class DatabaseManager:
    def __init__(self, db_path="greenhouse.db"):
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sensor_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    temp REAL,
                    humidity REAL,
                    vpd REAL,
                    solar_acc REAL,
                    moisture REAL
                )
            """)
            conn.commit()

    def save_data(self, data):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO sensor_data (temp, humidity, vpd, solar_acc, moisture)
                VALUES (?, ?, ?, ?, ?)
            """, (data['temp'], data['humidity'], data['vpd'], data['solar_accumulation'], data['moisture']))
            conn.commit()

    def get_history(self, limit=50):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM sensor_data ORDER BY timestamp DESC LIMIT ?", (limit,))
            return [dict(row) for row in cursor.fetchall()][::-1]
