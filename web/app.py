from flask import Flask, render_template, jsonify, request
import threading
import time
from core.logic import SystemControl
from interface.collector import DataCollector

app = Flask(__name__)

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
        state.control.process(data, collector=state.collector)
        time.sleep(2)

@app.route('/')
def index():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Hoogendoorn Control Dashboard</title>
        <style>
            body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 40px; background-color: #e8f5e9; }
            .container { max-width: 800px; margin: auto; }
            .card { background: white; padding: 25px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); margin-bottom: 20px; }
            .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
            .data-point { font-size: 28px; font-weight: bold; color: #1b5e20; }
            .label { color: #666; font-size: 14px; text-transform: uppercase; }
            h1 { color: #2e7d32; text-align: center; }
            .control-group { margin-top: 15px; }
            input { padding: 8px; border: 1px solid #ccc; border-radius: 4px; width: 100px; }
            button { padding: 10px 20px; cursor: pointer; background-color: #43a047; color: white; border: none; border-radius: 4px; font-weight: bold; }
            button:hover { background-color: #2e7d32; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Greenhouse Smart Control</h1>
            
            <div class="card">
                <h2>Real-time Monitoring</h2>
                <div class="grid">
                    <div>
                        <div class="label">Temperature</div>
                        <div id="temp" class="data-point">--</div>
                    </div>
                    <div>
                        <div class="label">VPD</div>
                        <div id="vpd" class="data-point">--</div>
                    </div>
                    <div>
                        <div class="label">Solar Accumulation</div>
                        <div id="solar_acc" class="data-point">--</div>
                        <div class="label" style="font-size: 10px;">J/cm²</div>
                    </div>
                    <div>
                        <div class="label">Soil Moisture</div>
                        <div id="moisture" class="data-point">--</div>
                    </div>
                </div>
            </div>

            <div class="card">
                <h2>Irrigation Settings (Hoogendoorn Logic)</h2>
                <div class="control-group">
                    <label>Solar Sum Threshold (J/cm²): </label>
                    <input type="number" id="solar_threshold" value="150">
                </div>
                <div class="control-group">
                    <label>Min Soil Moisture (%): </label>
                    <input type="number" id="moisture_threshold" value="30">
                </div>
                <div class="control-group">
                    <button onclick="updateSettings()">Apply Control Rules</button>
                </div>
            </div>
        </div>

        <script>
            function fetchData() {
                fetch('/api/data')
                    .then(response => response.json())
                    .then(data => {
                        document.getElementById('temp').innerText = data.temp + '°C';
                        document.getElementById('vpd').innerText = data.vpd + ' kPa';
                        document.getElementById('solar_acc').innerText = data.solar_accumulation;
                        document.getElementById('moisture').innerText = data.moisture + '%';
                    });
            }
            function updateSettings() {
                const solar = document.getElementById('solar_threshold').value;
                const moisture = document.getElementById('moisture_threshold').value;
                fetch('/api/settings', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        solar_threshold: parseFloat(solar),
                        moisture_threshold: parseFloat(moisture)
                    })
                }).then(() => alert('Hoogendoorn Rules Updated'));
            }
            setInterval(fetchData, 1000);
        </script>
    </body>
    </html>
    """

@app.route('/api/data')
def get_data():
    return jsonify(state.current_data)

@app.route('/api/settings', methods=['POST'])
def set_settings():
    state.control.update_setpoints(request.json)
    return jsonify({"status": "success"})

if __name__ == '__main__':
    t = threading.Thread(target=control_loop)
    t.daemon = True
    t.start()
    app.run(host='0.0.0.0', port=5000)
