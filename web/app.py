from flask import Flask, render_template, jsonify, request
import threading
import time
from core.logic import SystemControl
from interface.collector import DataCollector

app = Flask(__name__)

# Global state for sharing between control loop and web server
class SystemState:
    def __init__(self):
        self.current_data = {}
        self.control = SystemControl()
        self.collector = DataCollector()
        self.running = True

state = SystemState()

def control_loop():
    while state.running:
        data = state.collector.collect_signals()
        state.current_data = data
        state.control.process(data)
        time.sleep(5) # 5-second interval for logic processing

@app.route('/')
def index():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Berry_WHAT Greenhouse Dashboard</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; background-color: #f4f4f9; }
            .card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 20px; }
            .data-point { font-size: 24px; font-weight: bold; color: #2e7d32; }
            button { padding: 10px 20px; cursor: pointer; background-color: #2e7d32; color: white; border: none; border-radius: 4px; }
        </style>
    </head>
    <body>
        <h1>Greenhouse Monitoring & Control</h1>
        <div class="card">
            <h2>Current Status</h2>
            <div id="data">Loading...</div>
        </div>
        <div class="card">
            <h2>Control Settings</h2>
            <label>Target Temp: </label>
            <input type="number" id="temp_target" value="22" step="0.5">
            <button onclick="updateSettings()">Update</button>
        </div>
        <script>
            function fetchData() {
                fetch('/api/data')
                    .then(response => response.json())
                    .then(data => {
                        document.getElementById('data').innerHTML = 
                            '<p>Temperature: <span class="data-point">' + data.temp + 'C</span></p>' +
                            '<p>Humidity: <span class="data-point">' + data.humidity + '%</span></p>' +
                            '<p>VPD: <span class="data-point">' + data.vpd + ' kPa</span></p>' +
                            '<p>Soil Moisture: <span class="data-point">' + data.moisture + '%</span></p>';
                    });
            }
            function updateSettings() {
                const temp = document.getElementById('temp_target').value;
                fetch('/api/settings', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({target_temp: parseFloat(temp)})
                }).then(() => alert('Settings Updated'));
            }
            setInterval(fetchData, 2000);
        </script>
    </body>
    </html>
    """

@app.route('/api/data')
def get_data():
    return jsonify(state.current_data)

@app.route('/api/settings', methods=['POST'])
def set_settings():
    new_settings = request.json
    state.control.update_setpoints(new_settings)
    return jsonify({"status": "success"})

if __name__ == '__main__':
    # Start the control logic in a background thread
    t = threading.Thread(target=control_loop)
    t.daemon = True
    t.start()
    app.run(host='0.0.0.0', port=5000)
