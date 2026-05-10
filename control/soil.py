class SoilController:
    def __init__(self, mode="SIM", client=None):
        self.mode = mode
        self.client = client
        # 그룹 ID별 Modbus 코일 주소 매핑
        self.valve_map = {1: 4, 2: 5, 3: 6} 

    def irrigate(self, duration, line_id=1):
        coil_addr = self.valve_map.get(line_id, 4)
        if self.mode == "MODBUS" and self.client:
            self.client.write_coil(coil_addr, True)
        print(f"[Actuator: Soil] Line {line_id} ON for {duration}s (Coil: {coil_addr})")

    def stop_irrigation(self, line_id=1):
        coil_addr = self.valve_map.get(line_id, 4)
        if self.mode == "MODBUS" and self.client:
            self.client.write_coil(coil_addr, False)
        print(f"[Actuator: Soil] Line {line_id} OFF")
