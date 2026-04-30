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
                    moisture REAL,
                    ec REAL,
                    ph REAL,
                    water_content REAL
                )
            """)
            # 기존 테이블에 새 컬럼이 없을 경우를 대비해 ALTER TABLE 시도
            for col in ["ec", "ph", "water_content"]:
                try:
                    conn.execute(f"ALTER TABLE sensor_data ADD COLUMN {col} REAL")
                except sqlite3.OperationalError:
                    pass # 이미 컬럼이 있는 경우 무시
            conn.commit()

    def save_data(self, data):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO sensor_data (temp, humidity, vpd, solar_acc, moisture, ec, ph, water_content)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data['temp'], data['humidity'], data['vpd'], 
                data['solar_accumulation'], data['moisture'],
                data.get('ec', 0), data.get('ph', 0), data.get('water_content', 0)
            ))
            conn.commit()

    def get_history(self, limit=50):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM sensor_data ORDER BY timestamp DESC LIMIT ?", (limit,))
            return [dict(row) for row in cursor.fetchall()][::-1]
