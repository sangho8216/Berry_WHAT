from datetime import datetime
from control.air import AirController
from control.soil import SoilController

class SystemControl:
    def __init__(self):
        self.air = AirController()
        self.soil = SoilController()
        
        # 1. 기후 제어 설정 (Climate Control)
        self.climate_settings = {
            "target_temp": 22.0,
            "temp_deadband": 2.0,
            "target_vpd_min": 0.8,
            "target_vpd_max": 1.2
        }
        
        # 2. 양액/관수 제어 설정 (Nutrient Control - TCK22 Style)
        self.nutrient_settings = {
            "start_time": "08:00",
            "end_time": "18:00",
            "target_ec": 1.2,
            "target_ph": 5.8,
            "solar_threshold": 150.0,
            "min_moisture": 30.0,
            "duration": 60,
            "interval": 15,
            "control_mode": "복합제어",
            "control_code": "성장광",
            "manual_mode": False,
            "manual_valves": {"A": False, "B": False, "C": False, "ACID": False, "MAIN": False},
            "manual_pumps": {"MIXING": False, "SUPPLY": False}
        }
        
        self.last_irrigation_time = None
        self.today_supply_count = 0
        self.sunrise = "05:36"
        self.sunset = "19:18"
        
        # 통합 상태 관리
        self.actuator_status = {
            # 기후 계통
            "vents": "Closed", "fans": "Off", "heater": "Off", "misters": "Off",
            # 양액 계통
            "irrigation": "Off", "mixing_pump": "Off", "supply_pump": "Off",
            "valves": {"A": False, "B": False, "C": False, "ACID": False}
        }

    def _process_climate(self, data):
        temp = data.get("temp")
        vpd = data.get("vpd", 1.0)
        
        # 온도 제어
        if temp > self.climate_settings["target_temp"] + self.climate_settings["temp_deadband"]:
            self.air.adjust_environment("OPEN_VENTS")
            self.actuator_status["vents"] = "Open"
        elif temp < self.climate_settings["target_temp"] - self.climate_settings["temp_deadband"]:
            self.air.adjust_environment("CLOSE_VENTS")
            self.air.adjust_environment("START_HEATER")
            self.actuator_status["vents"] = "Closed"
            self.actuator_status["heater"] = "On"
        else:
            self.actuator_status["heater"] = "Off"

        # VPD 제어
        if vpd < self.climate_settings["target_vpd_min"]:
            self.air.adjust_environment("OPEN_VENTS")
            self.air.adjust_environment("START_HEATER")
            self.actuator_status["vents"] = "Open (Purge)"
            self.actuator_status["heater"] = "On (Reheat)"
        elif vpd > self.climate_settings["target_vpd_max"]:
            self.air.adjust_environment("START_MISTERS")
            self.actuator_status["misters"] = "On"
        else:
            self.actuator_status["misters"] = "Off"

    def _process_nutrient(self, data, collector):
        if self.nutrient_settings.get("manual_mode"):
            # 수동 모드: 설정된 개별 밸브/펌프 상태 반영
            mv = self.nutrient_settings["manual_valves"]
            mp = self.nutrient_settings["manual_pumps"]
            for v, s in mv.items(): self.soil.set_valve(v, s)
            for p, s in mp.items(): self.soil.set_pump(p, s)
            
            # 상태 업데이트
            self.actuator_status["irrigation"] = "Manual"
            self.actuator_status["mixing_pump"] = "On" if mp["MIXING"] else "Off"
            self.actuator_status["supply_pump"] = "On" if mp["SUPPLY"] else "Off"
            self.actuator_status["valves"].update(mv)
            return

        moisture = data.get("moisture")
        solar_acc = data.get("solar_accumulation")
        current_ec = data.get("ec")
        current_ph = data.get("ph")
        now = datetime.now()

        # 시간 윈도우 및 주기 확인
        can_irrigate = self.is_within_time_window()
        if self.last_irrigation_time:
            elapsed = (now - self.last_irrigation_time).total_seconds() / 60
            if elapsed < self.nutrient_settings["interval"]:
                can_irrigate = False

        triggered = False
        if can_irrigate:
            if solar_acc >= self.nutrient_settings["solar_threshold"]:
                print(f"[Nutrient] 일사 적산 도달 관수 실행")
                triggered = True
                if collector: collector.reset_solar_accumulation()
            elif moisture < self.nutrient_settings["min_moisture"]:
                print(f"[Nutrient] 최저 수분 도달 관수 실행")
                triggered = True

        if triggered:
            # EC/pH 보정
            if current_ec < self.nutrient_settings["target_ec"] - 0.05:
                self.soil.set_valve('A', True); self.soil.set_valve('B', True)
                self.actuator_status["valves"]["A"] = True; self.actuator_status["valves"]["B"] = True
            if current_ph > self.nutrient_settings["target_ph"] + 0.1:
                self.soil.set_valve('ACID', True)
                self.actuator_status["valves"]["ACID"] = True
            
            self.soil.set_pump('MIXING', True)
            self.soil.irrigate(self.nutrient_settings["duration"])
            self.last_irrigation_time = now
            self.today_supply_count += 1
            self.actuator_status["irrigation"] = "On"
        else:
            self.actuator_status["irrigation"] = "Off"
            self.actuator_status.update({"mixing_pump": "Off", "supply_pump": "Off"})
            for v in self.actuator_status["valves"]: self.actuator_status["valves"][v] = False

    def process(self, data, collector=None):
        self._process_climate(data)
        self._process_nutrient(data, collector)

    def is_within_time_window(self):
        now = datetime.now().time()
        start = datetime.strptime(self.nutrient_settings["start_time"], "%H:%M").time()
        end = datetime.strptime(self.nutrient_settings["end_time"], "%H:%M").time()
        return start <= now <= end

    def update_settings(self, new_settings):
        self.climate_settings.update({k: v for k, v in new_settings.items() if k in self.climate_settings})
        self.nutrient_settings.update({k: v for k, v in new_settings.items() if k in self.nutrient_settings})
        print(f"[Logic] 설정 업데이트 완료")

    def get_actuator_status(self):
        status = self.actuator_status.copy()
        status["today_supply"] = f"A그룹 {self.today_supply_count}회"
        status["sunrise"] = self.sunrise
        status["sunset"] = self.sunset
        return status

    def get_settings(self):
        return {**self.climate_settings, **self.nutrient_settings}
