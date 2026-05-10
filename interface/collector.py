import math
import time
import random
from abc import ABC, abstractmethod

class BaseCollector(ABC):
    @abstractmethod
    def collect_signals(self, actuator_status=None):
        pass

class SimulatedCollector(BaseCollector):
    def __init__(self):
        self.temp = 24.5
        self.humidity = 65.0
        self.moisture = 45.0
        self.solar_radiation = 400.0
        self.solar_accumulation = 0.0
        self.ec = 2.0
        self.ph = 5.8
        self.tank_a = 100.0   # %
        self.tank_b = 100.0   # %
        self.tank_acid = 100.0 # %
        self.last_time = time.time()

    def collect_signals(self, actuator_status=None):
        now = time.time()
        duration = now - self.last_time
        self.last_time = now
        
        # 일사 적산
        self.solar_accumulation += (self.solar_radiation * duration) / 10000.0
        
        # 탱크 소모 시뮬레이션 (펌프 작동 시)
        if actuator_status:
            if actuator_status.get("mixing_pump") == "On":
                self.tank_a -= 0.05 * duration
                self.tank_b -= 0.05 * duration
                self.tank_acid -= 0.02 * duration
        
        # 하한값 제한
        self.tank_a = max(0, self.tank_a)
        self.tank_b = max(0, self.tank_b)
        self.tank_acid = max(0, self.tank_acid)

        return {
            "temp": round(self.temp + random.uniform(-0.1, 0.1), 1),
            "humidity": round(self.humidity, 1),
            "moisture": round(self.moisture, 1),
            "solar_radiation": round(self.solar_radiation, 1),
            "solar_accumulation": round(self.solar_accumulation, 2),
            "ec": round(self.ec, 2),
            "ph": round(self.ph, 2),
            "tank_a": round(self.tank_a, 1),
            "tank_b": round(self.tank_b, 1),
            "tank_acid": round(self.tank_acid, 1),
            "flow_rate": round(self.flow_rate + random.uniform(-0.5, 0.5), 1),
            "water_temp": round(self.water_temp + random.uniform(-0.2, 0.2), 1),
            "mixing_tank_level": round(self.mixing_tank_level + random.uniform(-0.1, 0.1), 1),
            "vpd": self.calculate_vpd(self.temp, self.humidity)
        }

    def reset_solar_accumulation(self):
        self.solar_accumulation = 0.0

    def calculate_vpd(self, temp, humidity):
        es = 0.61078 * math.exp((17.27 * temp) / (temp + 237.3))
        ea = es * (humidity / 100.0)
        return round(es - ea, 3)

class ModbusCollector(BaseCollector):
    # Modbus 실구현체 (생략)
    def __init__(self, host="127.0.0.1", port=502): pass
    def collect_signals(self, actuator_status=None): return {"error": "Modbus Not Configured"}
    def reset_solar_accumulation(self): pass
