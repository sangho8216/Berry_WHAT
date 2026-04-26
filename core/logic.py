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
        self.solar_threshold = 150.0
        
        # Actuator State Tracking
        self.actuator_status = {
            "vents": "Closed",
            "fans": "Off",
            "heater": "Off",
            "irrigation": "Off"
        }

    def process(self, data, collector=None):
        temp = data.get("temp")
        moisture = data.get("moisture")
        solar_acc = data.get("solar_accumulation")
        
        # 1. Temperature Control logic
        if temp > self.target_temp + self.temp_deadband:
            self.air.adjust_environment("OPEN_VENTS")
            self.actuator_status["vents"] = "Open (Cooling)"
            self.actuator_status["fans"] = "On"
        elif temp < self.target_temp - self.temp_deadband:
            self.air.adjust_environment("CLOSE_VENTS")
            self.actuator_status["vents"] = "Closed"
            self.actuator_status["heater"] = "On"
        else:
            self.actuator_status["heater"] = "Off"
            self.actuator_status["fans"] = "Off"

        # 2. Irrigation Logic
        triggered = False
        if solar_acc >= self.solar_threshold or moisture < self.moisture_threshold:
            triggered = True
            if collector and solar_acc >= self.solar_threshold:
                collector.reset_solar_accumulation()

        if triggered:
            self.soil.irrigate(1.0)
            self.actuator_status["irrigation"] = "On (Watering)"
        else:
            self.actuator_status["irrigation"] = "Off"

    def get_actuator_status(self):
        return self.actuator_status

    def update_setpoints(self, setpoints):
        if "target_temp" in setpoints: self.target_temp = float(setpoints["target_temp"])
        if "moisture_threshold" in setpoints: self.moisture_threshold = float(setpoints["moisture_threshold"])
        if "solar_threshold" in setpoints: self.solar_threshold = float(setpoints["solar_threshold"])
