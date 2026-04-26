class SoilController:
    def __init__(self, mode="SIM", client=None):
        self.mode = mode
        self.client = client

    def irrigate(self, amount):
        if self.mode == "MODBUS" and self.client:
            self.client.write_coil(4, True) # 4번 코일을 밸브로 가정
        print(f"[Actuator: Soil ({self.mode})] Irrigating {amount}L")

    def stop_irrigation(self):
        if self.mode == "MODBUS" and self.client:
            self.client.write_coil(4, False)
        print(f"[Actuator: Soil ({self.mode})] Stopped")
