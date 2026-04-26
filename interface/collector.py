import math
import time

class DataCollector:
    def __init__(self):
        self.temp = 24.5
        self.humidity = 65.0
        self.moisture = 45.0
        self.solar_radiation = 400.0  # W/m2 (Current intensity)
        self.solar_accumulation = 0.0 # J/cm2 (Cumulative)
        self.last_time = time.time()

    def collect_signals(self):
        # Update solar accumulation (W/m2 * sec = Joules/m2. Convert to J/cm2 by / 10000)
        now = time.time()
        duration = now - self.last_time
        self.last_time = now
        
        # Incremental accumulation: (Watts * seconds) / 10000
        new_accumulation = (self.solar_radiation * duration) / 10000.0
        self.solar_accumulation += new_accumulation

        return {
            "temp": self.temp, 
            "humidity": self.humidity, 
            "moisture": self.moisture,
            "solar_radiation": self.solar_radiation,
            "solar_accumulation": round(self.solar_accumulation, 2),
            "vpd": self.calculate_vpd(self.temp, self.humidity)
        }

    def reset_solar_accumulation(self):
        self.solar_accumulation = 0.0

    def calculate_vpd(self, temp, humidity):
        es = 0.61078 * math.exp((17.27 * temp) / (temp + 237.3))
        ea = es * (humidity / 100.0)
        return round(es - ea, 3)
