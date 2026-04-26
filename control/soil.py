class SoilController:
    def irrigate(self, amount):
        print(f"[Actuator: Soil] Irrigating {amount}L of water to the greenhouse.")
    
    def stop_irrigation(self):
        print(f"[Actuator: Soil] Irrigation stopped.")
