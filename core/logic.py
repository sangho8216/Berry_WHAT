from datetime import datetime
from control.air import AirController
from control.soil import SoilController

class SystemControl:
    def __init__(self, db_manager):
        self.db = db_manager
        self.air = AirController()
        self.soil = SoilController()
        
        # 스킬 기반 대기 환경 설정
        self.target_temp = 22.0
        self.temp_deadband = 2.0
        self.target_vpd_min = 0.8  # kPa (스킬 권장 최소값)
        self.target_vpd_max = 1.2  # kPa (스킬 권장 최대값)
        
        self.refresh_groups()
        self.actuator_status = {
            "vents": "Closed", "fans": "Off", "heater": "Off",
            "misters": "Off", "mixing_pump": "Off", "supply_pump": "Off"
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
        vpd = data.get("vpd", 1.0)
        solar_rad = data.get("solar_radiation", 0)
        solar_acc = data.get("solar_accumulation", 0)
        moisture = data.get("moisture", 0)
        curr_ec = data.get("ec", 0)
        curr_ph = data.get("ph", 7)
        now = datetime.now()

        # 1. 스킬 기반 대기 & VPD 제어
        # 온도 제어 (Deadband)
        if temp > self.target_temp + self.temp_deadband:
            self.air.adjust_environment("OPEN_VENTS")
            self.actuator_status["vents"] = "Open (Cooling)"
        elif temp < self.target_temp - self.temp_deadband:
            self.air.adjust_environment("CLOSE_VENTS")
            self.actuator_status["vents"] = "Closed"
            self.actuator_status["heater"] = "On"
        else:
            self.actuator_status["heater"] = "Off"

        # VPD 제어 (습도 최적화)
        if vpd < self.target_vpd_min:
            # 너무 습함 -> 환기 증대 (Purge & Reheat)
            self.air.adjust_environment("INCREASE_VENTILATION")
            self.actuator_status["vents"] = "Purge (Dehumid)"
        elif vpd > self.target_vpd_max:
            # 너무 건조함 -> 미스트 가동
            self.air.adjust_environment("START_MISTERS")
            self.actuator_status["misters"] = "On"
        else:
            self.actuator_status["misters"] = "Off"

        # 2. 스킬 기반 관수 제어 (Multi-Group)
        any_watering = False
        for group in self.irrigation_groups:
            if not group["enabled"]:
                group["status"] = "Disabled"
                continue

            can_irrigate = self.is_within_time(group)
            
            # 휴지기 체크
            if group["last_irrigation_time"]:
                elapsed = (now - group["last_irrigation_time"]).total_seconds() / 60
                if elapsed < group["interval"]:
                    can_irrigate = False
                    group["status"] = f"Wait({int(group['interval']-elapsed)}m)"
            
            if group["status"] == "Watering":
                any_watering = True
                self._handle_fertigation(group, curr_ec, curr_ph)
                if (now - group["last_irrigation_time"]).total_seconds() >= group["duration"]:
                    group["status"] = "Ready"
                    self.soil.stop_irrigation(line_id=group["id"])
            
            elif can_irrigate:
                triggered = False
                # 일사 기반 (가중치: 일사 강도가 있을 때만 적산 유효성 판단 가능)
                if solar_acc >= group["solar_threshold"] and solar_rad > 50:
                    triggered = True
                    if collector: collector.reset_solar_accumulation()
                # 수분 기반 (안전 보장)
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
        self.actuator_status["supply_pump"] = "On"
        self.actuator_status["mixing_pump"] = "On"

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
