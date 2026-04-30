class SoilController:
    def __init__(self, mode="SIM", client=None):
        self.mode = mode
        self.client = client

    def set_pump(self, pump_type, state):
        """
        pump_type: 'MIXING', 'SUPPLY'
        state: True (On), False (Off)
        """
        coil_map = {'MIXING': 10, 'SUPPLY': 11}
        if self.mode == "MODBUS" and self.client:
            self.client.write_coil(coil_map.get(pump_type), state)
        print(f"[Actuator: Soil ({self.mode})] Pump {pump_type} set to {state}")

    def set_valve(self, valve_name, state):
        """
        valve_name: 'A', 'B', 'C', 'ACID', 'MAIN'
        """
        coil_map = {'A': 20, 'B': 21, 'C': 22, 'ACID': 23, 'MAIN': 24}
        if self.mode == "MODBUS" and self.client:
            self.client.write_coil(coil_map.get(valve_name), state)
        print(f"[Actuator: Soil ({self.mode})] Valve {valve_name} set to {state}")

    def irrigate(self, duration, ec_target=None, ph_target=None):
        # 기존 단일 밸브 제어 호환성 유지 및 확장
        print(f"[Actuator: Soil ({self.mode})] Starting irrigation sequence for {duration}s")
        self.set_valve('MAIN', True)
        self.set_pump('SUPPLY', True)

    def stop_irrigation(self):
        self.set_valve('MAIN', False)
        self.set_pump('SUPPLY', False)
        self.set_pump('MIXING', False)
        print(f"[Actuator: Soil ({self.mode})] Stopped")
