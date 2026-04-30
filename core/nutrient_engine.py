from enum import Enum, auto
from datetime import datetime

class NutrientState(Enum):
    STANDBY = 0
    PRE_RINSE = 1
    MIXING = 2
    STABILIZATION = 3
    IRRIGATION = 4
    POST_RINSE = 5
    ALARM = 6

class NutrientEngine:
    def __init__(self, soil_controller):
        self.state = NutrientState.STANDBY
        self.soil = soil_controller
        self.state_start_time = datetime.now()
        
        # P-Control gains
        self.kp_ec = 5.0
        self.kp_ph = 2.0
        
        # Thresholds
        self.ec_tolerance = 0.05
        self.ph_tolerance = 0.05
        self.max_ec_limit = 4.0
        
        self.current_recipe = {
            "target_ec": 1.5,
            "target_ph": 5.8,
            "duration": 60,
            "rinse_duration": 10
        }

    def set_recipe(self, target_ec, target_ph, duration):
        self.current_recipe["target_ec"] = target_ec
        self.current_recipe["target_ph"] = target_ph
        self.current_recipe["duration"] = duration

    def get_state_name(self):
        return self.state.name

    def step(self, data):
        current_ec = data.get("ec", 0.0)
        current_ph = data.get("ph", 7.0)
        now = datetime.now()
        elapsed = (now - self.state_start_time).total_seconds()

        # Safety Check
        if current_ec > self.max_ec_limit:
            self.state = NutrientState.ALARM

        if self.state == NutrientState.STANDBY:
            self._stop_all()
            
        elif self.state == NutrientState.PRE_RINSE:
            self.soil.set_pump('MIXING', True)
            self.soil.set_pump('SUPPLY', True)
            if elapsed > self.current_recipe["rinse_duration"]:
                self._transition_to(NutrientState.MIXING)

        elif self.state == NutrientState.MIXING:
            self.soil.set_pump('MIXING', True)
            self.soil.set_pump('SUPPLY', False)
            
            # EC Control (A/B Tanks)
            if current_ec < self.current_recipe["target_ec"] - self.ec_tolerance:
                self.soil.set_valve('A', True)
                self.soil.set_valve('B', True)
            else:
                self.soil.set_valve('A', False)
                self.soil.set_valve('B', False)
                
            # pH Control (Acid)
            if current_ph > self.current_recipe["target_ph"] + self.ph_tolerance:
                self.soil.set_valve('ACID', True)
            else:
                self.soil.set_valve('ACID', False)
                
            # Check if stabilized
            ec_ok = abs(current_ec - self.current_recipe["target_ec"]) < self.ec_tolerance
            ph_ok = abs(current_ph - self.current_recipe["target_ph"]) < self.ph_tolerance
            if ec_ok and ph_ok:
                self._transition_to(NutrientState.STABILIZATION)

        elif self.state == NutrientState.STABILIZATION:
            self._stop_valves()
            self.soil.set_pump('MIXING', True)
            if elapsed > 10: # Wait for 10 seconds to ensure stability
                self._transition_to(NutrientState.IRRIGATION)

        elif self.state == NutrientState.IRRIGATION:
            self.soil.set_pump('MIXING', True)
            self.soil.set_pump('SUPPLY', True)
            if elapsed > self.current_recipe["duration"]:
                self._transition_to(NutrientState.POST_RINSE)

        elif self.state == NutrientState.POST_RINSE:
            self._stop_valves()
            self.soil.set_pump('MIXING', False)
            self.soil.set_pump('SUPPLY', True)
            if elapsed > self.current_recipe["rinse_duration"]:
                self._transition_to(NutrientState.STANDBY)

        elif self.state == NutrientState.ALARM:
            self._stop_all()
            # Requires manual reset or condition fix

    def trigger_irrigation(self):
        if self.state == NutrientState.STANDBY:
            self._transition_to(NutrientState.PRE_RINSE)

    def _transition_to(self, new_state):
        print(f"[NutrientEngine] State Transition: {self.state.name} -> {new_state.name}")
        self.state = new_state
        self.state_start_time = datetime.now()

    def _stop_all(self):
        self.soil.set_pump('MIXING', False)
        self.soil.set_pump('SUPPLY', False)
        self._stop_valves()

    def _stop_valves(self):
        for v in ['A', 'B', 'C', 'ACID']:
            self.soil.set_valve(v, False)
