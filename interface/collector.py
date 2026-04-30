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
        self.ec = 1.46
        self.ph = 5.44
        self.flow_rate = 161.0
        self.water_content = 62.0
        self.solar_radiation = 400.0
        self.solar_accumulation = 0.0
        self.last_time = time.time()

    def collect_signals(self):
        now = time.time()
        duration = now - self.last_time
        self.last_time = now
        
        # 1. 일사 적산
        self.solar_accumulation += (self.solar_radiation * duration) / 10000.0
        
        # 2. 액추에이터 상태에 따른 변화 (가정된 외부 상태를 가져올 수 없으므로 내부 상태 추적 필요)
        # 여기서는 단순화를 위해 random 기반에 약간의 경향성 추가
        import random
        
        # 관수 중일 때 수분 증가, EC/pH 변화
        # (실제로는 engine의 actuator_status를 참조해야 하지만 구조상 독립적임)
        # 간단한 랜덤 드리프트
        self.temp += random.uniform(-0.05, 0.05)
        self.moisture -= 0.01 * duration # 자연 건조
        self.ec += random.uniform(-0.005, 0.005)
        self.ph += random.uniform(-0.01, 0.01)
        
        return {
            "temp": round(self.temp, 1), 
            "humidity": round(self.humidity, 1), 
            "moisture": round(max(0, self.moisture), 1),
            "ec": round(self.ec, 2),
            "ph": round(self.ph, 2),
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
