class AirController:
    def __init__(self, mode="SIM", client=None):
        self.mode = mode
        self.client = client # Modbus Client

    def adjust_environment(self, action):
        if self.mode == "MODBUS" and self.client:
            self._modbus_control(action)
        
        print(f"[Actuator: Air ({self.mode})] Executing: {action}")

    def _modbus_control(self, action):
        # 예시: 액션에 따른 Modbus 코일 쓰기
        coil_map = {"OPEN_VENTS": 0, "CLOSE_VENTS": 1, "START_FANS": 2, "START_HEATER": 3}
        if action in coil_map:
            self.client.write_coil(coil_map[action], True)
