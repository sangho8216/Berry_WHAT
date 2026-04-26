from control.air import AirController
from control.soil import SoilController

class SystemControl:
    def __init__(self):
        self.air = AirController()
        self.soil = SoilController()
        
        # Default Setpoints
        self.target_temp = 22.0
        self.temp_deadband = 2.0
        self.target_vpd_min = 0.8
        self.target_vpd_max = 1.2
        self.moisture_threshold = 30.0

    def process(self, data):
        temp = data.get("temp")
        humidity = data.get("humidity")
        moisture = data.get("moisture")
        vpd = data.get("vpd")
        
        print(f"[Logic] Processing: Temp={temp}C, Hum={humidity}%, VPD={vpd}kPa, Soil={moisture}%")
        
        # 1. Temperature Control
        if temp > self.target_temp + self.temp_deadband:
            self.air.adjust_environment("OPEN_VENTS")
            self.air.adjust_environment("START_FANS")
        elif temp < self.target_temp - self.temp_deadband:
            self.air.adjust_environment("CLOSE_VENTS")
            self.air.adjust_environment("START_HEATER")
        else:
            self.air.adjust_environment("OPTIMAL_TEMP_MAINTAINED")

        # 2. Humidity (VPD) Control
        if vpd < self.target_vpd_min:
            print("[Logic] VPD too low (Too Humid). Triggering Purge & Reheat.")
            self.air.adjust_environment("INCREASE_VENTILATION")
        elif vpd > self.target_vpd_max:
            print("[Logic] VPD too high (Too Dry). Triggering Fogging/Misting.")
            self.air.adjust_environment("START_MISTERS")

        # 3. Irrigation Control
        if moisture < self.moisture_threshold:
            self.soil.irrigate(1.0) # 1.0 Liter
        else:
            print("[Logic] Soil moisture optimal.")

    def update_setpoints(self, setpoints):
        if "target_temp" in setpoints: self.target_temp = setpoints["target_temp"]
        if "moisture_threshold" in setpoints: self.moisture_threshold = setpoints["moisture_threshold"]
        print(f"[Logic] Setpoints updated: {setpoints}")
