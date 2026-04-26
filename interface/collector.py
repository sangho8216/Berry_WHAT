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
        self.solar_radiation = 400.0
        self.solar_accumulation = 0.0
        self.last_time = time.time()

    def collect_signals(self):
        now = time.time()
        duration = now - self.last_time
        self.last_time = now
        self.solar_accumulation += (self.solar_radiation * duration) / 10000.0
        
        return {
            "temp": self.temp, "humidity": self.humidity, "moisture": self.moisture,
            "solar_radiation": self.solar_radiation, "solar_accumulation": round(self.solar_accumulation, 2),
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
