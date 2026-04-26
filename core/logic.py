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
        
        # Hoogendoorn Style Irrigation Settings
        self.moisture_threshold = 30.0  # %
        self.solar_threshold = 150.0    # J/cm2 (Target for irrigation)

    def process(self, data, collector=None):
        temp = data.get("temp")
        vpd = data.get("vpd")
        moisture = data.get("moisture")
        solar_acc = data.get("solar_accumulation")
        
        print(f"[Logic] Temp: {temp}C, VPD: {vpd}kPa, Soil: {moisture}%, SolarAcc: {solar_acc}J/cm2")
        
        # 1. Temperature & Humidity (Air Control)
        if temp > self.target_temp + self.temp_deadband:
            self.air.adjust_environment("OPEN_VENTS")
        elif temp < self.target_temp - self.temp_deadband:
            self.air.adjust_environment("CLOSE_VENTS")

        # 2. Irrigation Control (Hoogendoorn Logic)
        triggered = False
        # Rule A: Solar Accumulation Threshold
        if solar_acc >= self.solar_threshold:
            print(f"[Logic] Solar Sum reached ({solar_acc} >= {self.solar_threshold}). Triggering Irrigation.")
            triggered = True
            if collector: collector.reset_solar_accumulation()
            
        # Rule B: Critical Soil Moisture (Safety Override)
        elif moisture < self.moisture_threshold:
            print(f"[Logic] Soil moisture critical ({moisture}% < {self.moisture_threshold}%). Triggering Irrigation.")
            triggered = True

        if triggered:
            self.soil.irrigate(1.0)
        else:
            print("[Logic] Irrigation conditions not met.")

    def update_setpoints(self, setpoints):
        if "target_temp" in setpoints: self.target_temp = float(setpoints["target_temp"])
        if "moisture_threshold" in setpoints: self.moisture_threshold = float(setpoints["moisture_threshold"])
        if "solar_threshold" in setpoints: self.solar_threshold = float(setpoints["solar_threshold"])
        print(f"[Logic] Setpoints updated: {setpoints}")
