import math

class DataCollector:
    def __init__(self):
        # Initial simulation values
        self.temp = 24.5
        self.humidity = 65.0
        self.moisture = 45.0

    def collect_signals(self):
        # Placeholder for Modbus/Sensor collection
        # In a real scenario, this would read from sensors
        return {
            "temp": self.temp, 
            "humidity": self.humidity, 
            "moisture": self.moisture,
            "vpd": self.calculate_vpd(self.temp, self.humidity)
        }

    def calculate_vpd(self, temp, humidity):
        """
        Calculates Vapor Pressure Deficit (VPD) in kPa.
        Formula: VPD = es - ea
        es (Saturated Vapor Pressure) = 0.61078 * exp((17.27 * T) / (T + 237.3))
        ea (Actual Vapor Pressure) = es * (RH / 100)
        """
        es = 0.61078 * math.exp((17.27 * temp) / (temp + 237.3))
        ea = es * (humidity / 100.0)
        vpd = es - ea
        return round(vpd, 3)
