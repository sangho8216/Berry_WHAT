from flask import Flask, render_template, jsonify, request
import threading
import time
import os
from core.logic import SystemControl
from interface.collector import SimulatedCollector, ModbusCollector
from core.db import DatabaseManager

app = Flask(__name__)

class SystemState:
    def __init__(self):
        self.mode = os.getenv("CONTROL_MODE", "SIM")
        self.collector = ModbusCollector() if self.mode == "MODBUS" else SimulatedCollector()
        self.control = SystemControl()
        self.db = DatabaseManager()
        self.current_data = {}
        self.running = True

state = SystemState()

def control_loop():
    while state.running:
        data = state.collector.collect_signals()
        if "error" not in data:
            data["status"] = "Connected"
            state.current_data = data
            state.control.process(data, collector=state.collector)
        time.sleep(2)

@app.route('/')
def index():
    # JS Template literal (backticks) handled carefully within heredoc
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Berry_WHAT 멀티구역 제어 시스템</title>
        <style>
            body { font-family: 'Malgun Gothic', sans-serif; margin: 40px; background-color: #f4f7f4; }
            .container { max-width: 1200px; margin: auto; }
            .card { background: white; padding: 20px; border-radius: 12px; box-shadow: 0 2px 10px rgba(0,0,0,0.05); margin-bottom: 20px; }
            .group-list { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
            .group-card { border: 1px solid #eee; padding: 15px; border-radius: 8px; position: relative; }
            .status-tag { position: absolute; top: 15px; right: 15px; padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: bold; }
            .tag-ready { background: #e3f2fd; color: #1976d2; }
            .tag-watering { background: #e8f5e9; color: #2e7d32; animation: blink 1s infinite; }
            .tag-disabled { background: #f5f5f5; color: #9e9e9e; }
            @keyframes blink { 50% { opacity: 0.5; } }
            .switch { position: relative; display: inline-block; width: 40px; height: 20px; }
            .switch input { opacity: 0; width: 0; height: 0; }
            .slider { position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0; background-color: #ccc; transition: .4s; border-radius: 20px; }
            .slider:before { position: absolute; content: ""; height: 16px; width: 16px; left: 2px; bottom: 2px; background-color: white; transition: .4s; border-radius: 50%; }
            input:checked + .slider { background-color: #4caf50; }
            input:checked + .slider:before { transform: translateX(20px); }
            h2 { color: #2e7d32; margin-top: 0; }
            .grid-env { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-bottom: 20px; }
            .env-box { background: #fff; padding: 10px; border-radius: 8px; text-align: center; border: 1px solid #e0eee0; }
            .val { font-size: 20px; font-weight: bold; display: block; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🌿 구역별 관수 및 장치 모니터링</h1>
            
            <div class="grid-env">
                <div class="env-box"><span>내부 온도</span><b id="temp" class="val">--</b></div>
                <div class="env-box"><span>포차(VPD)</span><b id="vpd" class="val">--</b></div>
                <div class="env-box"><span>일사적산</span><b id="solar" class="val">--</b></div>
                <div class="env-box"><span>토양수분</span><b id="moist" class="val">--</b></div>
            </div>

            <div class="group-list" id="group-container">
                <!-- 그룹 카드가 여기에 동적으로 생성됨 -->
            </div>
        </div>

        <script>
            function updateUI() {
                fetch('/api/data').then(r => r.json()).then(data => {
                    document.getElementById('temp').innerText = (data.temp || 0) + '°C';
                    document.getElementById('vpd').innerText = (data.vpd || 0) + ' kPa';
                    document.getElementById('solar').innerText = data.solar_accumulation || 0;
                    document.getElementById('moist').innerText = (data.moisture || 0) + '%';
                });

                fetch('/api/groups').then(r => r.json()).then(groups => {
                    const container = document.getElementById('group-container');
                    let html = '';
                    groups.forEach(g => {
                        const tagClass = g.status.toLowerCase().includes('water') ? 'tag-watering' : (g.enabled ? 'tag-ready' : 'tag-disabled');
                        html += '<div class="card group-card">' +
                                '<span class="status-tag ' + tagClass + '">' + g.status + '</span>' +
                                '<h2>' + g.name + '</h2>' +
                                '<div style="margin-bottom: 10px;">' +
                                '활성화: <label class="switch">' +
                                '<input type="checkbox" ' + (g.enabled ? 'checked' : '') + ' onchange="toggleGroup(' + g.id + ', this.checked)">' +
                                '<span class="slider"></span></label></div>' +
                                '<div style="font-size: 13px; color: #666;">' +
                                '설정: 일사 ' + g.solar_threshold + 'J | 수분 ' + g.min_moisture + '% | 시간 ' + g.duration + '초' +
                                '</div></div>';
                    });
                    container.innerHTML = html;
                });
            }

            function toggleGroup(id, enabled) {
                fetch('/api/groups/toggle', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({id, enabled})
                });
            }

            setInterval(updateUI, 2000);
            updateUI();
        </script>
    </body>
    </html>
    """

@app.route('/api/groups')
def get_groups():
    return jsonify(state.control.get_irrigation_status())

@app.route('/api/groups/toggle', methods=['POST'])
def toggle_group():
    data = request.json
    state.control.update_group_settings(data['id'], {"enabled": data['enabled']})
    return jsonify({"status": "success"})

@app.route('/api/data')
def get_data():
    return jsonify(state.current_data)

if __name__ == '__main__':
    t = threading.Thread(target=control_loop)
    t.daemon = True
    t.start()
    app.run(host='0.0.0.0', port=5000)
