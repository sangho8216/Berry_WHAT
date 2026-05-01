import sqlite3
from datetime import datetime

class DatabaseManager:
    def __init__(self, db_path="greenhouse.db"):
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            # 센서 데이터 테이블
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sensor_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    temp REAL, humidity REAL, vpd REAL, solar_acc REAL, moisture REAL
                )
            """)
            # 관수 그룹 설정 테이블
            conn.execute("""
                CREATE TABLE IF NOT EXISTS irrigation_groups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    enabled BOOLEAN DEFAULT 1,
                    start_time TEXT DEFAULT '08:00',
                    end_time TEXT DEFAULT '18:00',
                    solar_threshold REAL DEFAULT 150.0,
                    min_moisture REAL DEFAULT 30.0,
                    duration INTEGER DEFAULT 60,
                    interval INTEGER DEFAULT 15
                )
            """)
            # 기본 그룹 생성 (비어있을 경우)
            cursor = conn.execute("SELECT count(*) FROM irrigation_groups")
            if cursor.fetchone()[0] == 0:
                conn.execute("INSERT INTO irrigation_groups (name) VALUES ('기본 구역')")
            conn.commit()

    def save_sensor_data(self, data):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO sensor_data (temp, humidity, vpd, solar_acc, moisture)
                VALUES (?, ?, ?, ?, ?)
            """, (data.get('temp'), data.get('humidity'), data.get('vpd'), data.get('solar_accumulation'), data.get('moisture')))
            conn.commit()

    def get_history(self, limit=50):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM sensor_data ORDER BY timestamp DESC LIMIT ?", (limit,))
            return [dict(row) for row in cursor.fetchall()][::-1]

    # 그룹 관리 CRUD
    def get_groups(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            return [dict(row) for row in conn.execute("SELECT * FROM irrigation_groups").fetchall()]

    def add_group(self, name):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("INSERT INTO irrigation_groups (name) VALUES (?)", (name,))
            conn.commit()
            return cursor.lastrowid

    def update_group(self, group_id, settings):
        keys = settings.keys()
        query = f"UPDATE irrigation_groups SET {', '.join([f'{k} = ?' for k in keys])} WHERE id = ?"
        values = list(settings.values()) + [group_id]
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(query, values)
            conn.commit()

    def delete_group(self, group_id):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM irrigation_groups WHERE id = ?", (group_id,))
            conn.commit()
