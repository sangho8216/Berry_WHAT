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
        self.target_vpd_min = 0.8
        self.target_vpd_max = 1.2
        
        self.refresh_groups()
        self.actuator_status = {
            "vents": "Closed", "fans": "Off", "heater": "Off",
            "misters": "Off", "mixing_pump": "Off", "supply_pump": "Off"
        }

    def refresh_groups(self):
        db_groups = self.db.get_groups()
        self.irrigation_groups = []
        for g in db_groups:
            # 상태값 초기화
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

        # 1. 대기 제어 (이전과 동일)
        if temp > self.target_temp + self.temp_deadband:
            self.air.adjust_environment("OPEN_VENTS")
            self.actuator_status["vents"] = "Open"
        elif temp < self.target_temp - self.temp_deadband:
            self.air.adjust_environment("CLOSE_VENTS")
            self.actuator_status["vents"] = "Closed"

        # 2. 고도화된 멀티 구역 관수 로직
        any_watering = False
        for group in self.irrigation_groups:
            if not group["enabled"]:
                group["status"] = "Disabled"
                continue

            can_irrigate = self.is_within_time(group)
            
            # 휴지기 체크
            elapsed_min = 0
            if group["last_irrigation_time"]:
                elapsed_min = (now - group["last_irrigation_time"]).total_seconds() / 60
                if elapsed_min < group["interval"]:
                    can_irrigate = False
                    group["status"] = f"Wait({int(group['interval']-elapsed_min)}m)"
            
            if group["status"] == "Watering":
                any_watering = True
                self._handle_fertigation(group, curr_ec, curr_ph)
                
                # 관수 시간 + 후수 시간 체크
                total_duration = group["duration"] + group["rinse_duration"]
                if (now - group["last_irrigation_time"]).total_seconds() >= total_duration:
                    group["status"] = "Ready"
                    self.soil.stop_irrigation(line_id=group["id"])
            
            elif can_irrigate:
                triggered = False
                trigger_reason = ""

                # 조건 1: 일사 적산 기반 (최소 일사 강도 조건 포함)
                if solar_acc >= group["solar_threshold"] and solar_rad >= group["min_radiation"]:
                    triggered = True
                    trigger_reason = "Solar Sum"
                    if collector: collector.reset_solar_accumulation()
                
                # 조건 2: 최대 휴지 시간 초과 (백업 타이머)
                elif group["last_irrigation_time"] and elapsed_min >= group["fixed_interval"]:
                    triggered = True
                    trigger_reason = "Fixed Interval"
                
                # 조건 3: 최저 토양 수분 (비상)
                elif moisture < group["min_moisture"]:
                    triggered = True
                    trigger_reason = "Low Moisture"

                if triggered:
                    print(f"[Logic] {group['name']} 관수 시작: {trigger_reason}")
                    group["status"] = "Watering"
                    group["last_irrigation_time"] = now
                    self.soil.irrigate(group["duration"], line_id=group["id"])
                    any_watering = True
                else:
                    group["status"] = "Monitoring"

        if not any_watering:
            self.actuator_status["mixing_pump"] = "Off"
            self.actuator_status["supply_pump"] = "Off"

    def _handle_fertigation(self, group, curr_ec, curr_ph):
        # 후수 시간(rinse_duration) 동안은 믹싱 펌프를 끄고 공급 펌프만 가동 가능 (생략)
        self.actuator_status["supply_pump"] = "On"
        self.actuator_status["mixing_pump"] = "On"

    def get_irrigation_status(self): return self.irrigation_groups
    def get_actuator_status(self): return self.actuator_status
    def add_group(self, name): self.db.add_group(name); self.refresh_groups()
    def delete_group(self, group_id): self.db.delete_group(group_id); self.refresh_groups()
    def update_group(self, group_id, settings): self.db.update_group(group_id, settings); self.refresh_groups()
