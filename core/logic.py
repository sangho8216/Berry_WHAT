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
        
        self.refresh_groups()
        # 공조 및 공용 장치 상태
        self.actuator_status = {
            "vents": "Closed", "fans": "Off", "heater": "Off",
            "mixing_pump": "Off", "supply_pump": "Off"
        }

    def refresh_groups(self):
        db_groups = self.db.get_groups()
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
        temp = data.get("temp", 20)
        curr_ec = data.get("ec", 0)
        curr_ph = data.get("ph", 7)
        now = datetime.now()

        # 1. 공조 제어
        if temp > self.target_temp + self.temp_deadband:
            self.air.adjust_environment("OPEN_VENTS")
            self.actuator_status["vents"] = "Open"
        elif temp < self.target_temp - self.temp_deadband:
            self.air.adjust_environment("CLOSE_VENTS")
            self.actuator_status["vents"] = "Closed"

        # 2. 통합 관수 및 양액 제어
        solar_acc = data.get("solar_accumulation", 0)
        moisture = data.get("moisture", 0)
        
        any_watering = False

        for group in self.irrigation_groups:
            if not group["enabled"]:
                group["status"] = "Disabled"
                continue

            # 휴지기 및 시간 윈도우 체크
            can_irrigate = self.is_within_time(group)
            if group["last_irrigation_time"]:
                elapsed = (now - group["last_irrigation_time"]).total_seconds() / 60
                if elapsed < group["interval"]:
                    can_irrigate = False
                    group["status"] = f"Wait({int(group['interval']-elapsed)}m)"
            
            if group["status"] == "Watering":
                # 현재 관수 중인 경우 믹싱 및 공급 펌프 작동
                any_watering = True
                self._handle_fertigation(group, curr_ec, curr_ph)
                
                # 관수 시간 종료 체크 (간단한 예시를 위해 60초 후 종료 가정)
                if (now - group["last_irrigation_time"]).total_seconds() >= group["duration"]:
                    group["status"] = "Ready"
                    self.soil.stop_irrigation(line_id=group["id"])
            
            elif can_irrigate:
                triggered = False
                if solar_acc >= group["solar_threshold"]:
                    triggered = True
                    if collector: collector.reset_solar_accumulation()
                elif moisture < group["min_moisture"]:
                    triggered = True

                if triggered:
                    group["status"] = "Watering"
                    group["last_irrigation_time"] = now
                    self.soil.irrigate(group["duration"], line_id=group["id"])
                    any_watering = True
                else:
                    group["status"] = "Ready"

        if not any_watering:
            self.actuator_status["mixing_pump"] = "Off"
            self.actuator_status["supply_pump"] = "Off"

    def _handle_fertigation(self, group, curr_ec, curr_ph):
        """양액 농도(EC) 및 산도(pH) 조절 로직"""
        self.actuator_status["supply_pump"] = "On"
        self.actuator_status["mixing_pump"] = "On"
        
        # EC 조절 (A/B액 투입)
        if curr_ec < group["target_ec"] - 0.1:
            # Modbus 등으로 A/B 밸브 제어 코드 가능
            pass 
        
        # pH 조절 (산성액 투입)
        if curr_ph > group["target_ph"] + 0.1:
            pass

    def get_actuator_status(self):
        return self.actuator_status

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
