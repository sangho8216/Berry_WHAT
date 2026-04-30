import math
import time
from abc import ABC, abstractmethod

class BaseCollector(ABC):
    @abstractmethod
    def collect_signals(self):
        pass

class SimulatedCollector(BaseCollector):
    def __init__(self):
        self.temp = 24.5
        self.humidity = 65.0
        self.moisture = 45.0
        self.ec = 0.8  # Start with lower EC
        self.ph = 7.0  # Start with neutral pH
        self.flow_rate = 0.0
        self.water_content = 62.0
        self.solar_radiation = 400.0
        self.solar_accumulation = 0.0
        self.last_time = time.time()

    def collect_signals(self, actuator_status=None):
        now = time.time()
        duration = now - self.last_time
        self.last_time = now
        
        # 1. 일사 적산
        self.solar_accumulation += (self.solar_radiation * duration) / 10000.0
        
        # 2. 액추에이터 상태에 따른 물리 시뮬레이션
        import random
        
        if actuator_status:
            # 펌프 상태 확인
            mixing_on = actuator_status.get("mixing_pump") == "On"
            supply_on = actuator_status.get("supply_pump") == "On"
            valves = actuator_status.get("valves", {})
            
            # 믹싱 효과 (EC/pH 변화)
            if mixing_on:
                if valves.get("A") or valves.get("B"):
                    self.ec += 0.02 * duration  # A/B 밸브 열림 -> EC 상승
                if valves.get("ACID"):
                    self.ph -= 0.05 * duration  # Acid 밸브 열림 -> pH 하락
                
                # 자연적인 안정화 (믹싱 펌프가 돌면 균일해짐)
                self.ec += random.uniform(-0.001, 0.001)
                self.ph += random.uniform(-0.002, 0.002)
            
            # 관수 효과 (수분량 변화)
            if supply_on:
                self.moisture += 0.5 * duration
                self.flow_rate = 150.0 + random.uniform(-5, 5)
            else:
                self.flow_rate = 0.0
        
        # 자연 건조 및 온도 변화
        self.temp += random.uniform(-0.05, 0.05)
        self.moisture -= 0.02 * duration 
        self.moisture = max(0, min(100, self.moisture))
        
        # EC/pH 자연 드리프트 (믹싱 안 할 때)
        if not (actuator_status and actuator_status.get("mixing_pump") == "On"):
            self.ec += random.uniform(-0.002, 0.002)
            self.ph += random.uniform(-0.002, 0.002)

        return {
            "temp": round(self.temp, 1), 
            "humidity": round(self.humidity, 1), 
            "moisture": round(self.moisture, 1),
            "ec": round(max(0.1, self.ec), 2),
            "ph": round(max(1.0, min(14.0, self.ph)), 2),
            "flow_rate": round(self.flow_rate, 1),
            "water_content": round(self.water_content, 1),
            "solar_radiation": round(self.solar_radiation, 1), 
            "solar_accumulation": round(self.solar_accumulation, 2),
            "vpd": self.calculate_vpd(self.temp, self.humidity)
        }


    def reset_solar_accumulation(self):
        self.solar_accumulation = 0.0

    def calculate_vpd(self, temp, humidity):
        es = 0.61078 * math.exp((17.27 * temp) / (temp + 237.3))
        ea = es * (humidity / 100.0)
        return round(es - ea, 3)

class ModbusCollector(BaseCollector):
    def __init__(self, host="127.0.0.1", port=502):
        from pymodbus.client import ModbusTcpClient
        self.client = ModbusTcpClient(host, port)
        self.solar_accumulation = 0.0
        self.last_time = time.time()

    def collect_signals(self):
        if not self.client.connect():
            return {"error": "Modbus Connection Failed"}
        
        # 예시: 레지스터 0~3번에서 데이터 읽기 (온도, 습도, 수분, 일사)
        result = self.client.read_holding_registers(0, 4)
        if result.isError():
            return {"error": "Modbus Read Failed"}

        raw_temp, raw_hum, raw_moist, raw_solar = result.registers
        temp = raw_temp / 10.0
        hum = raw_hum / 10.0
        moist = raw_moist / 10.0
        solar = float(raw_solar)

        now = time.time()
        self.solar_accumulation += (solar * (now - self.last_time)) / 10000.0
        self.last_time = now

        return {
            "temp": temp, "humidity": hum, "moisture": moist,
            "solar_radiation": solar, "solar_accumulation": round(self.solar_accumulation, 2),
            "vpd": round(0.61078 * math.exp((17.27 * temp) / (temp + 237.3)) * (1 - hum/100.0), 3)
        }

    def reset_solar_accumulation(self):
        self.solar_accumulation = 0.0
