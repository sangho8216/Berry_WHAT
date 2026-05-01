import sqlite3
from datetime import datetime

class DatabaseManager:
    def __init__(self, db_path="greenhouse.db"):
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            # 센서 데이터 (탱크 잔량 추가)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sensor_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    temp REAL, humidity REAL, vpd REAL, solar_acc REAL, moisture REAL,
                    ec REAL, ph REAL, tank_a REAL, tank_b REAL, tank_acid REAL
                )
            """)
            # 관수 그룹 설정
            conn.execute("""
                CREATE TABLE IF NOT EXISTS irrigation_groups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    enabled BOOLEAN DEFAULT 1,
                    start_time TEXT DEFAULT '08:00',
                    end_time TEXT DEFAULT '18:00',
                    solar_threshold REAL DEFAULT 150.0,
                    min_radiation REAL DEFAULT 50.0,
                    fixed_interval INTEGER DEFAULT 120,
                    min_moisture REAL DEFAULT 30.0,
                    target_ec REAL DEFAULT 2.0,
                    target_ph REAL DEFAULT 5.8,
                    duration INTEGER DEFAULT 60,
                    rinse_duration INTEGER DEFAULT 10,
                    interval INTEGER DEFAULT 15
                )
            """)
            # 시스템 설정 (대기 환경 등)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS system_config (
                    key TEXT PRIMARY KEY,
                    value REAL
                )
            """)
            conn.commit()

    def save_sensor_data(self, data):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO sensor_data (temp, humidity, vpd, solar_acc, moisture, ec, ph, tank_a, tank_b, tank_acid)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (data.get('temp'), data.get('humidity'), data.get('vpd'), data.get('solar_accumulation'), 
                  data.get('moisture'), data.get('ec'), data.get('ph'), 
                  data.get('tank_a'), data.get('tank_b'), data.get('tank_acid')))
            conn.commit()

    def get_config(self, key, default):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT value FROM system_config WHERE key = ?", (key,))
            row = cursor.fetchone()
            return row[0] if row else default

    def set_config(self, key, value):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("INSERT OR REPLACE INTO system_config (key, value) VALUES (?, ?)", (key, value))
            conn.commit()

    def get_groups(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            return [dict(row) for row in conn.execute("SELECT * FROM irrigation_groups").fetchall()]

    def update_group(self, group_id, settings):
        keys = settings.keys()
        query = f"UPDATE irrigation_groups SET {', '.join([f'{k} = ?' for k in keys])} WHERE id = ?"
        values = list(settings.values()) + [group_id]
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(query, values)
            conn.commit()
    
    # ... (add_group, delete_group, get_history stay same)
    def add_group(self, name):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("INSERT INTO irrigation_groups (name) VALUES (?)", (name,))
            conn.commit()
            return cursor.lastrowid
    def delete_group(self, group_id):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM irrigation_groups WHERE id = ?", (group_id,))
            conn.commit()
    def get_history(self, limit=50):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM sensor_data ORDER BY timestamp DESC LIMIT ?", (limit,))
            return [dict(row) for row in cursor.fetchall()][::-1]
