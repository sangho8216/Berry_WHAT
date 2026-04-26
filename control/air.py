class AirController:
    def adjust_environment(self, action):
        actions = {
            "OPEN_VENTS": "Vents opened for cooling/ventilation.",
            "CLOSE_VENTS": "Vents closed to retain heat.",
            "START_FANS": "Fans activated for air circulation.",
            "STOP_FANS": "Fans deactivated.",
            "START_HEATER": "Heater activated.",
            "STOP_HEATER": "Heater deactivated.",
            "START_MISTERS": "Misters activated for humidity increase.",
            "INCREASE_VENTILATION": "Vents opened wider for dehumidification.",
            "OPTIMAL_TEMP_MAINTAINED": "Temperature is within optimal range."
        }
        status = actions.get(action, f"Executing unknown action: {action}")
        print(f"[Actuator: Air] {status}")
