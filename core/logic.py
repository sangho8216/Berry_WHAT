from datetime import datetime
from control.air import AirController
from control.soil import SoilController

class SystemControl:
    def __init__(self):
        self.air = AirController()
        self.soil = SoilController()
        
        # 기본 환경 설정
        self.target_temp = 22.0
        self.temp_deadband = 2.0
        
        # 양액/관수 세부 설정 (Hoogendoorn Style)
        self.irrigation_settings = {
            "start_time": "08:00",    # 관수 시작 가능 시간
            "end_time": "18:00",      # 관수 종료 시간
            "target_ec": 2.5,         # 목표 EC
            "target_ph": 5.8,         # 목표 pH
            "solar_threshold": 150.0, # 일사 적산 임계값 (J/cm2)
            "min_moisture": 30.0,     # 최저 토양 수분 (%)
            "duration": 60,           # 1회 관수 시간 (초)
            "interval": 15            # 관수 간 최소 휴지 시간 (분)
        }
        
        self.last_irrigation_time = None
        self.actuator_status = {
            "vents": "Closed", "fans": "Off", "heater": "Off", "irrigation": "Off"
        }

    def is_within_time_window(self):
        now = datetime.now().time()
        start = datetime.strptime(self.irrigation_settings["start_time"], "%H:%M").time()
        end = datetime.strptime(self.irrigation_settings["end_time"], "%H:%M").time()
        return start <= now <= end

    def process(self, data, collector=None):
        temp = data.get("temp")
        moisture = data.get("moisture")
        solar_acc = data.get("solar_accumulation")
        now = datetime.now()

        # 1. 온도 제어
        if temp > self.target_temp + self.temp_deadband:
            self.air.adjust_environment("OPEN_VENTS")
            self.actuator_status["vents"] = "Open"
        elif temp < self.target_temp - self.temp_deadband:
            self.air.adjust_environment("CLOSE_VENTS")
            self.actuator_status["vents"] = "Closed"

        # 2. 관수/양액 제어 (시간 윈도우 및 주기 확인)
        can_irrigate = self.is_within_time_window()
        
        # 휴지 시간 확인
        if self.last_irrigation_time:
            elapsed = (now - self.last_irrigation_time).total_seconds() / 60
            if elapsed < self.irrigation_settings["interval"]:
                can_irrigate = False

        triggered = False
        if can_irrigate:
            if solar_acc >= self.irrigation_settings["solar_threshold"]:
                print(f"[Logic] 일사 적산 도달 관수 실행")
                triggered = True
                if collector: collector.reset_solar_accumulation()
            elif moisture < self.irrigation_settings["min_moisture"]:
                print(f"[Logic] 최저 수분 도달 관수 실행")
                triggered = True

        if triggered:
            self.soil.irrigate(self.irrigation_settings["duration"])
            self.last_irrigation_time = now
            self.actuator_status["irrigation"] = f"On ({self.irrigation_settings['duration']}s)"
        else:
            self.actuator_status["irrigation"] = "Off"

    def update_settings(self, new_settings):
        self.irrigation_settings.update(new_settings)
        if "target_temp" in new_settings:
            self.target_temp = float(new_settings["target_temp"])
        print(f"[Logic] 설정 업데이트 완료: {self.irrigation_settings}")

    def get_actuator_status(self):
        return self.actuator_status

    def get_settings(self):
        settings = self.irrigation_settings.copy()
        settings["target_temp"] = self.target_temp
        return settings
