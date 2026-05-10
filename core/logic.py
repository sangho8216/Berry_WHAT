from datetime import datetime
import time
from control.air import AirController
from control.soil import SoilController

class SystemControl:
    # State constants based on nutrient-solution-expert skill
    STANDBY = "STANDBY"
    PRE_RINSE = "PRE_RINSE"
    MIXING = "MIXING"
    STABILIZATION = "STABILIZATION"
    IRRIGATION = "IRRIGATION"
    POST_RINSE = "POST_RINSE"
    ALARM = "ALARM"

    def __init__(self, db_manager):
        self.db = db_manager
        self.air = AirController()
        self.soil = SoilController()
        
        # Air settings
        self.target_temp = self.db.get_config("target_temp", 22.0)
        self.temp_deadband = self.db.get_config("temp_deadband", 2.0)
        self.target_vpd_min = self.db.get_config("target_vpd_min", 0.8)
        self.target_vpd_max = self.db.get_config("target_vpd_max", 1.2)
        
        # PID & Fertigation Settings
        self.target_water_temp = float(self.db.get_config("target_water_temp", 20.0))
        self.ec_p_band = float(self.db.get_config("ec_p_band", 10.0))
        self.ph_p_band = float(self.db.get_config("ph_p_band", 10.0))
        self.flow_pre_control = float(self.db.get_config("flow_pre_control", 50.0))
        
        self.refresh_groups()
        
        # Fertigation State Machine
        self.current_state = self.STANDBY
        self.active_group = None
        self.state_start_time = None
        
        self.actuator_status = {
            "vents": "Closed", "fans": "Off", "heater": "Off",
            "misters": "Off", "mixing_pump": "Off", "supply_pump": "Off",
            "mixing_valve": "Closed",
            "state": self.STANDBY
        }

    def refresh_groups(self):
        db_groups = self.db.get_groups()
        self.irrigation_groups = []
        for g in db_groups:
            g["status"] = "Ready"
            g["last_irrigation_time"] = None
            self.irrigation_groups.append(g)

    def _transition_to(self, new_state, group=None):
        print(f"[State] {self.current_state} -> {new_state}")
        self.current_state = new_state
        self.state_start_time = time.time()
        self.actuator_status["state"] = new_state
        if group:
            self.active_group = group
            group["status"] = new_state

    def process(self, data, collector=None):
        temp = data.get("temp", 20)
        vpd = data.get("vpd", 1.0)
        solar_rad = data.get("solar_radiation", 0)
        solar_acc = data.get("solar_accumulation", 0)
        moisture = data.get("moisture", 0)
        curr_ec = data.get("ec", 0)
        curr_ph = data.get("ph", 7)
        ec_temp = data.get("ec_temp", 25.0)
        now = datetime.now()

        # 1. Atmospheric Control (Remains independent)
        self._handle_air_control(temp, vpd)

        # 2. Fertigation Expert State Machine
        if self.current_state == self.STANDBY:
            for group in self.irrigation_groups:
                if not group["enabled"]: continue
                
                # Check timing and interval
                can_run = self._check_timing(group, now)
                if not can_run: continue

                # Check triggers (Solar Sum or Moisture)
                if solar_acc >= group["solar_threshold"] or moisture < group["min_moisture"]:
                    if collector and solar_acc >= group["solar_threshold"]:
                        collector.reset_solar_accumulation()
                    self._transition_to(self.PRE_RINSE, group)
                    break

        elif self.current_state == self.PRE_RINSE:
            self.actuator_status["supply_pump"] = "On"
            if time.time() - self.state_start_time > 10: # 10s Pre-rinse
                self._transition_to(self.MIXING, self.active_group)

        elif self.current_state == self.MIXING:
            self.actuator_status["mixing_pump"] = "On"
            # Expert Logic: Proportional Dosing (Simulated here)
            target_ec = self._get_dynamic_ec(self.active_group, solar_rad)
            if abs(curr_ec - target_ec) < 0.1 and abs(curr_ph - self.active_group["target_ph"]) < 0.2:
                self._transition_to(self.STABILIZATION, self.active_group)

        elif self.current_state == self.STABILIZATION:
            if time.time() - self.state_start_time > 5: # 5s Stabilize
                self._transition_to(self.IRRIGATION, self.active_group)

        elif self.current_state == self.IRRIGATION:
            self.soil.irrigate(self.active_group["duration"], line_id=self.active_group["id"])
            if time.time() - self.state_start_time > self.active_group["duration"]:
                self.soil.stop_irrigation(line_id=self.active_group["id"])
                self._transition_to(self.POST_RINSE, self.active_group)

        elif self.current_state == self.POST_RINSE:
            self.actuator_status["mixing_pump"] = "Off"
            if time.time() - self.state_start_time > self.active_group.get("rinse_duration", 10):
                self.active_group["last_irrigation_time"] = now
                self.active_group["status"] = "Ready"
                self._transition_to(self.STANDBY)

        # Safety: Alarm Check
        if curr_ec > 4.0 or curr_ph < 3.0:
            self._transition_to(self.ALARM)
            self.actuator_status["supply_pump"] = "Off"
            self.actuator_status["mixing_pump"] = "Off"

    def _handle_air_control(self, temp, vpd):
        if temp > self.target_temp + self.temp_deadband:
            self.air.adjust_environment("OPEN_VENTS")
            self.actuator_status["vents"] = "Open"
        elif temp < self.target_temp - self.temp_deadband:
            self.air.adjust_environment("CLOSE_VENTS")
            self.actuator_status["vents"] = "Closed"
            self.actuator_status["heater"] = "On"
        else:
            self.actuator_status["heater"] = "Off"

        if vpd < self.target_vpd_min:
            self.actuator_status["vents"] = "Purge (VPD)"
        elif vpd > self.target_vpd_max:
            self.actuator_status["misters"] = "On"
        else:
            self.actuator_status["misters"] = "Off"

    def _check_timing(self, group, now):
        start = datetime.strptime(group["start_time"], "%H:%M").time()
        end = datetime.strptime(group["end_time"], "%H:%M").time()
        if not (start <= now.time() <= end): return False
        
        if group["last_irrigation_time"]:
            elapsed = (now - group["last_irrigation_time"]).total_seconds() / 60
            if elapsed < group["interval"]: return False
        return True

    def _get_dynamic_ec(self, group, solar_rad):
        # Expert logic: Adjust EC based on light intensity
        # High light -> plants drink more water -> lower EC target
        base_ec = group["target_ec"]
        if solar_rad > 600: return base_ec - 0.2
        if solar_rad < 200: return base_ec + 0.2
        return base_ec

    def get_actuator_status(self): return self.actuator_status
    def get_irrigation_status(self): return self.irrigation_groups
    def add_group(self, name): self.db.add_group(name); self.refresh_groups()
    def delete_group(self, group_id): self.db.delete_group(group_id); self.refresh_groups()
    def update_group(self, group_id, settings): self.db.update_group(group_id, settings); self.refresh_groups()
