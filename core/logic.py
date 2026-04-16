class SystemControl:
    def __init__(self):
        self.rules = "Default Recipe"
        
    def process(self, data):
        print(f"Processing data with {self.rules}: {data}")
        # Logic to trigger control modules based on rules
