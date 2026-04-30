from datetime import datetime
from control.air import AirController
from control.soil import SoilController
from core.nutrient_engine import NutrientEngine, NutrientState

class SystemControl:
    def __init__(self):
        self.air = AirController()
        self.soil = SoilController()
        self.nutrient_engine = NutrientEngine(self.soil)
        
        # 1. 기후 제어 설정 (Climate Control)
        self.climate_settings = {
            "target_temp": 22.0,
            "temp_deadband": 2.0,
            "target_vpd_min": 0.8,
            "target_vpd_max": 1.2
        }
        
        # 2. 양액/관수 제어 설정 (Nutrient Control - v3.0 Standard)
        self.nutrient_settings = {
            "start_time": "06:00",
            "end_time": "20:00",
            "target_ec": 1.5,
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
            "valves": {"A": False, "B": False, "C": False, "ACID": False},
            "nutrient_state": "STANDBY"
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
        # 엔진 레시피 업데이트
        self.nutrient_engine.set_recipe(
            self.nutrient_settings["target_ec"],
            self.nutrient_settings["target_ph"],
            self.nutrient_settings["duration"]
        )

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
            self.actuator_status["nutrient_state"] = "MANUAL"
            return

        # 자동 제어 트리거 로직
        moisture = data.get("moisture")
        solar_acc = data.get("solar_accumulation")
        now = datetime.now()

        if self.nutrient_engine.state == NutrientState.STANDBY:
            can_irrigate = self.is_within_time_window()
            if self.last_irrigation_time:
                elapsed = (now - self.last_irrigation_time).total_seconds() / 60
                if elapsed < self.nutrient_settings["interval"]:
                    can_irrigate = False

            if can_irrigate:
                if solar_acc >= self.nutrient_settings["solar_threshold"]:
                    print(f"[Nutrient] 일사 적산 도달 관수 실행")
                    self.nutrient_engine.trigger_irrigation()
                    if collector: collector.reset_solar_accumulation()
                    self.last_irrigation_time = now
                    self.today_supply_count += 1
                elif moisture < self.nutrient_settings["min_moisture"]:
                    print(f"[Nutrient] 최저 수분 도달 관수 실행")
                    self.nutrient_engine.trigger_irrigation()
                    self.last_irrigation_time = now
                    self.today_supply_count += 1

        # 엔진 스텝 실행
        self.nutrient_engine.step(data)

        # 상태 업데이트 (엔진 상태 및 액추에이터 상태 동기화)
        self.actuator_status["nutrient_state"] = self.nutrient_engine.get_state_name()
        self.actuator_status["irrigation"] = "On" if self.nutrient_engine.state != NutrientState.STANDBY else "Off"
        
        # 개별 액추에이터 상태는 엔진에서 직접 제어하지만 UI 표시를 위해 업데이트
        # (실제 하드웨어 상태를 읽어오는 것이 좋으나 여기선 엔진의 의도 반영)
        self.actuator_status["mixing_pump"] = "On" if self.nutrient_engine.state in [NutrientState.PRE_RINSE, NutrientState.MIXING, NutrientState.STABILIZATION, NutrientState.IRRIGATION] else "Off"
        self.actuator_status["supply_pump"] = "On" if self.nutrient_engine.state in [NutrientState.PRE_RINSE, NutrientState.IRRIGATION, NutrientState.POST_RINSE] else "Off"
        
        # 밸브 상태 (MIXING 단계에서만 A/B/ACID 활성화 가능)
        if self.nutrient_engine.state == NutrientState.MIXING:
            current_ec = data.get("ec", 0.0)
            current_ph = data.get("ph", 7.0)
            self.actuator_status["valves"]["A"] = current_ec < self.nutrient_settings["target_ec"] - 0.05
            self.actuator_status["valves"]["B"] = self.actuator_status["valves"]["A"]
            self.actuator_status["valves"]["ACID"] = current_ph > self.nutrient_settings["target_ph"] + 0.05
        else:
            for v in ["A", "B", "ACID"]: self.actuator_status["valves"][v] = False


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
