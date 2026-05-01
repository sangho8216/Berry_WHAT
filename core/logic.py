from datetime import datetime
from control.air import AirController
from control.soil import SoilController

class SystemControl:
    def __init__(self, db_manager):
        self.db = db_manager
        self.air = AirController()
        self.soil = SoilController()
        
        self.target_temp = 22.0
        self.temp_deadband = 2.0
        
        # DB에서 그룹 로드 및 상태 초기화
        self.refresh_groups()
        self.actuator_status = {"vents": "Closed", "fans": "Off", "heater": "Off"}

    def refresh_groups(self):
        db_groups = self.db.get_groups()
        # 실시간 상태(status, last_irrigation_time)는 메모리에서 관리
        self.irrigation_groups = []
        for g in db_groups:
            g["status"] = "Ready"
            g["last_irrigation_time"] = None
            self.irrigation_groups.append(g)

    def is_within_time(self, group):
        now = datetime.now().time()
        start = datetime.strptime(group["start_time"], "%H:%M").time()
        end = datetime.strptime(group["end_time"], "%H:%M").time()
        return start <= now <= end

    def process(self, data, collector=None):
        temp = data.get("temp")
        now = datetime.now()

        # 공조 제어
        if temp > self.target_temp + self.temp_deadband:
            self.air.adjust_environment("OPEN_VENTS")
            self.actuator_status["vents"] = "Open"
        elif temp < self.target_temp - self.temp_deadband:
            self.air.adjust_environment("CLOSE_VENTS")
            self.actuator_status["vents"] = "Closed"

        # 그룹별 관수 제어
        solar_acc = data.get("solar_accumulation", 0)
        moisture = data.get("moisture", 0)

        for group in self.irrigation_groups:
            if not group["enabled"]:
                group["status"] = "Disabled"
                continue

            if group["status"] not in ["Watering", "Disabled"]:
                group["status"] = "Ready"

            can_irrigate = self.is_within_time(group)
            
            if group["last_irrigation_time"]:
                elapsed = (now - group["last_irrigation_time"]).total_seconds() / 60
                if elapsed < group["interval"]:
                    can_irrigate = False
                    group["status"] = f"Wait({int(group['interval']-elapsed)}m)"

            triggered = False
            if can_irrigate:
                if solar_acc >= group["solar_threshold"]:
                    triggered = True
                    if collector: collector.reset_solar_accumulation()
                elif moisture < group["min_moisture"]:
                    triggered = True

            if triggered:
                self.soil.irrigate(group["duration"], line_id=group["id"])
                group["last_irrigation_time"] = now
                group["status"] = "Watering"
            elif can_irrigate and group["status"] == "Ready":
                group["status"] = "Monitoring"

    def get_irrigation_status(self):
        return self.irrigation_groups

    def add_group(self, name):
        self.db.add_group(name)
        self.refresh_groups()

    def delete_group(self, group_id):
        self.db.delete_group(group_id)
        self.refresh_groups()

    def update_group(self, group_id, settings):
        self.db.update_group(group_id, settings)
        self.refresh_groups()
