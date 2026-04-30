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
            "target_ec": 1.2,         # 목표 EC (이미지 기준)
            "target_ph": 5.8,         # 목표 pH (이미지 기준)
            "solar_threshold": 150.0, # 일사 적산 임계값 (J/cm2)
            "min_moisture": 30.0,     # 최저 토양 수분 (%)
            "duration": 60,           # 1회 관수 시간 (초)
            "interval": 15,           # 관수 간 최소 휴지 시간 (분)
            "control_mode": "복합제어", # 제어 방식
            "control_code": "성장광"    # 제어 코드
        }
        
        self.last_irrigation_time = None
        self.today_supply_count = 0
        self.sunrise = "05:36"
        self.sunset = "19:18"
        self.actuator_status = {
            "vents": "Closed", "fans": "Off", "heater": "Off", "irrigation": "Off",
            "mixing_pump": "Off", "supply_pump": "Off"
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
        current_ec = data.get("ec")
        current_ph = data.get("ph")
        now = datetime.now()

        # 1. 온도 제어
        temp_triggered = False
        if temp > self.target_temp + self.temp_deadband:
            self.air.adjust_environment("OPEN_VENTS")
            self.actuator_status["vents"] = "Open"
            temp_triggered = True
        elif temp < self.target_temp - self.temp_deadband:
            self.air.adjust_environment("CLOSE_VENTS")
            self.actuator_status["vents"] = "Closed"
            self.air.adjust_environment("START_HEATER")
            self.actuator_status["heater"] = "On"
            temp_triggered = True
        else:
            self.actuator_status["heater"] = "Off"

        # 2. VPD (포차) 제어 (스킬 기반)
        vpd = data.get("vpd", 1.0)
        if vpd < 0.8: # 습도가 너무 높음
            print(f"[Logic] 저포차(Low VPD: {vpd}) 감지: 제습 및 재가열")
            self.air.adjust_environment("OPEN_VENTS")
            self.air.adjust_environment("START_HEATER")
            self.actuator_status["vents"] = "Open (Purge)"
            self.actuator_status["heater"] = "On (Reheat)"
        elif vpd > 1.2: # 너무 건조함
            print(f"[Logic] 고포차(High VPD: {vpd}) 감지: 미스트 가동")
            self.air.adjust_environment("START_MISTERS")
            self.actuator_status["misters"] = "On"
        else:
            self.actuator_status["misters"] = "Off"

        # 3. 관수/양액 제어 (시간 윈도우 및 주기 확인)
        can_irrigate = self.is_within_time_window()
        
        # 휴지 시간 확인
        if self.last_irrigation_time:
            elapsed = (now - self.last_irrigation_time).total_seconds() / 60
            if elapsed < self.irrigation_settings["interval"]:
                can_irrigate = False

        triggered = False
        if can_irrigate:
            if solar_acc >= self.irrigation_settings["solar_threshold"]:
                print(f"[Logic] 일사 적산({solar_acc}J/cm2) 도달 관수 실행")
                triggered = True
                if collector: collector.reset_solar_accumulation()
            elif moisture < self.irrigation_settings["min_moisture"]:
                print(f"[Logic] 최저 수분({moisture}%) 도달 관수 실행")
                triggered = True

        if triggered:
            # 양액 농도 조절 로직 (TCK22 스타일)
            # EC가 낮으면 A, B 밸브 가동, pH가 높으면 Acid 밸브 가동
            if current_ec < self.irrigation_settings["target_ec"] - 0.05:
                print(f"[Logic] EC 낮음 ({current_ec}): 비료(A/B) 투입 시작")
                self.soil.set_valve('A', True)
                self.soil.set_valve('B', True)
            elif current_ec > self.irrigation_settings["target_ec"] + 0.05:
                print(f"[Logic] EC 높음 ({current_ec}): 희석(물) 비율 증가")
                self.soil.set_valve('A', False)
                self.soil.set_valve('B', False)

            if current_ph > self.irrigation_settings["target_ph"] + 0.1:
                print(f"[Logic] pH 높음 ({current_ph}): 산(Acid) 투입")
                self.soil.set_valve('ACID', True)
            else:
                self.soil.set_valve('ACID', False)

            self.soil.set_pump('MIXING', True)
            self.soil.irrigate(self.irrigation_settings["duration"])
            self.last_irrigation_time = now
            self.today_supply_count += 1
            self.actuator_status["irrigation"] = f"On ({self.irrigation_settings['duration']}s)"
            self.actuator_status["mixing_pump"] = "On"
            self.actuator_status["supply_pump"] = "On"
        else:
            self.actuator_status["irrigation"] = "Off"
            self.actuator_status["mixing_pump"] = "Off"
            self.actuator_status["supply_pump"] = "Off"
            # 밸브 초기화
            self.soil.set_valve('A', False)
            self.soil.set_valve('B', False)
            self.soil.set_valve('ACID', False)
            self.soil.set_valve('MAIN', False)

    def update_settings(self, new_settings):
        self.irrigation_settings.update(new_settings)
        if "target_temp" in new_settings:
            self.target_temp = float(new_settings["target_temp"])
        print(f"[Logic] 설정 업데이트 완료: {self.irrigation_settings}")

    def get_actuator_status(self):
        status = self.actuator_status.copy()
        status["today_supply"] = f"A그룹 {self.today_supply_count}회"
        status["sunrise"] = self.sunrise
        status["sunset"] = self.sunset
        return status

    def get_settings(self):
        settings = self.irrigation_settings.copy()
        settings["target_temp"] = self.target_temp
        return settings
