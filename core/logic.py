from datetime import datetime
from control.air import AirController
from control.soil import SoilController

class SystemControl:
    def __init__(self):
        self.air = AirController()
        self.soil = SoilController()
        
        self.target_temp = 22.0
        self.temp_deadband = 2.0
        
        # 관수 그룹 설정 (Hoogendoorn Valve Groups)
        self.irrigation_groups = [
            {
                "id": 1, "name": "A구역 (딸기)", "enabled": True,
                "start_time": "08:00", "end_time": "18:00",
                "solar_threshold": 150.0, "min_moisture": 30.0,
                "duration": 60, "interval": 15,
                "last_irrigation_time": None, "status": "Ready"
            },
            {
                "id": 2, "name": "B구역 (토마토)", "enabled": False,
                "start_time": "07:00", "end_time": "19:00",
                "solar_threshold": 200.0, "min_moisture": 25.0,
                "duration": 120, "interval": 30,
                "last_irrigation_time": None, "status": "Ready"
            }
        ]
        
        self.actuator_status = {"vents": "Closed", "fans": "Off", "heater": "Off"}

    def is_within_time(self, group):
        now = datetime.now().time()
        start = datetime.strptime(group["start_time"], "%H:%M").time()
        end = datetime.strptime(group["end_time"], "%H:%M").time()
        return start <= now <= end

    def process(self, data, collector=None):
        temp = data.get("temp")
        now = datetime.now()

        # 1. 공조 제어
        if temp > self.target_temp + self.temp_deadband:
            self.air.adjust_environment("OPEN_VENTS")
            self.actuator_status["vents"] = "Open"
        elif temp < self.target_temp - self.temp_deadband:
            self.air.adjust_environment("CLOSE_VENTS")
            self.actuator_status["vents"] = "Closed"

        # 2. 그룹별 관수 제어
        solar_acc = data.get("solar_accumulation", 0)
        moisture = data.get("moisture", 0)

        for group in self.irrigation_groups:
            if not group["enabled"]:
                group["status"] = "Disabled"
                continue

            # 기본 상태는 Ready
            if group["status"] not in ["Watering", "Disabled"]:
                group["status"] = "Ready"

            can_irrigate = self.is_within_time(group)
            
            # 휴지 시간 체크
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
                self.soil.irrigate(group["duration"])
                group["last_irrigation_time"] = now
                group["status"] = "Watering"
            elif can_irrigate and group["status"] == "Ready":
                group["status"] = "Monitoring"

    def update_group_settings(self, group_id, new_settings):
        for group in self.irrigation_groups:
            if group["id"] == group_id:
                group.update(new_settings)
                break

    def get_actuator_status(self):
        return self.actuator_status

    def get_irrigation_status(self):
        return self.irrigation_groups
