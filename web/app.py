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
        self.db = DatabaseManager()
        self.collector = ModbusCollector() if self.mode == "MODBUS" else SimulatedCollector()
        self.control = SystemControl(self.db)
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
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Berry_WHAT 정밀 양액 제어 시스템</title>
        <style>
            body { font-family: 'Malgun Gothic', sans-serif; margin: 30px; background-color: #f0f2f0; }
            .container { max-width: 1200px; margin: auto; }
            .card { background: white; padding: 20px; border-radius: 12px; box-shadow: 0 4px 10px rgba(0,0,0,0.05); margin-bottom: 20px; }
            .grid-env { display: grid; grid-template-columns: repeat(6, 1fr); gap: 10px; margin-bottom: 20px; }
            .env-box { background: #fff; padding: 12px; border-radius: 8px; text-align: center; border: 1px solid #d0e0d0; }
            .val { font-size: 20px; font-weight: bold; color: #2e7d32; display: block; }
            .group-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
            .group-card { border: 1px solid #eee; padding: 15px; border-radius: 10px; position: relative; }
            .status-tag { position: absolute; top: 15px; right: 15px; padding: 4px 10px; border-radius: 20px; font-size: 11px; font-weight: bold; }
            .tag-watering { background: #e8f5e9; color: #2e7d32; animation: blink 1s infinite; }
            .tag-ready { background: #e3f2fd; color: #1976d2; }
            @keyframes blink { 50% { opacity: 0.5; } }
            .input-small { width: 60px; padding: 4px; border: 1px solid #ddd; border-radius: 4px; }
            .label { font-size: 11px; color: #666; margin-top: 5px; }
            button.save-btn { background: #4caf50; color: white; border: none; padding: 6px 12px; border-radius: 4px; cursor: pointer; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🌿 Berry_WHAT 통합 양액 및 환경제어</h1>
            
            <div class="grid-env">
                <div class="env-box"><span>온도</span><b id="temp" class="val">--</b></div>
                <div class="env-box"><span>VPD</span><b id="vpd" class="val">--</b></div>
                <div class="env-box"><span>일사적산</span><b id="solar" class="val">--</b></div>
                <div class="env-box"><span>수분</span><b id="moist" class="val">--</b></div>
                <div class="env-box"><span>EC</span><b id="ec" class="val">--</b></div>
                <div class="env-box"><span>pH</span><b id="ph" class="val">--</b></div>
            </div>

            <div class="card">
                <div style="display:flex; justify-content:space-between; margin-bottom:15px;">
                    <h2>관수 구역 및 양액 설정</h2>
                    <button onclick="addGroup()">+ 구역 추가</button>
                </div>
                <div class="group-grid" id="group-container"></div>
            </div>
        </div>

        <script>
            function updateUI() {
                fetch('/api/data').then(r => r.json()).then(data => {
                    document.getElementById('temp').innerText = (data.temp || 0) + '°C';
                    document.getElementById('vpd').innerText = (data.vpd || 0) + ' kPa';
                    document.getElementById('solar').innerText = data.solar_accumulation || 0;
                    document.getElementById('moist').innerText = (data.moisture || 0) + '%';
                    document.getElementById('ec').innerText = (data.ec || 0) + ' dS/m';
                    document.getElementById('ph').innerText = (data.ph || 0);
                });

                fetch('/api/groups').then(r => r.json()).then(groups => {
                    const container = document.getElementById('group-container');
                    let html = '';
                    groups.forEach(g => {
                        const tagClass = g.status.toLowerCase().includes('water') ? 'tag-watering' : 'tag-ready';
                        html += '<div class="group-card">' +
                                '<span class="status-tag ' + tagClass + '">' + g.status + '</span>' +
                                '<h3>' + g.name + '</h3>' +
                                '<div style="display:grid; grid-template-columns: 1fr 1fr; gap: 10px; font-size: 13px;">' +
                                '<div><label class="label">목표 EC</label><br><input class="input-small" id="ec-' + g.id + '" value="' + g.target_ec + '"></div>' +
                                '<div><label class="label">목표 pH</label><br><input class="input-small" id="ph-' + g.id + '" value="' + g.target_ph + '"></div>' +
                                '<div><label class="label">일사 임계</label><br><input class="input-small" id="solar-' + g.id + '" value="' + g.solar_threshold + '"></div>' +
                                '<div><label class="label">최저 수분</label><br><input class="input-small" id="moist-' + g.id + '" value="' + g.min_moisture + '"></div>' +
                                '</div>' +
                                '<div style="margin-top: 15px;">' +
                                '<button class="save-btn" onclick="saveGroup(' + g.id + ')">설정 저장</button>' +
                                '<button onclick="deleteGroup(' + g.id + ')" style="background:none; border:none; color:red; cursor:pointer; font-size:12px; margin-left:10px;">삭제</button>' +
                                '</div>' +
                                '</div>';
                    });
                    container.innerHTML = html;
                });
            }

            function saveGroup(id) {
                const settings = {
                    target_ec: parseFloat(document.getElementById('ec-' + id).value),
                    target_ph: parseFloat(document.getElementById('ph-' + id).value),
                    solar_threshold: parseFloat(document.getElementById('solar-' + id).value),
                    min_moisture: parseFloat(document.getElementById('moist-' + id).value)
                };
                fetch('/api/groups/update', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({id, settings}) })
                .then(() => alert('설정 저장됨'));
            }

            function addGroup() {
                const name = prompt("구역 이름:");
                if(name) fetch('/api/groups/add', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({name}) }).then(updateUI);
            }
            function deleteGroup(id) {
                if(confirm("삭제하시겠습니까?")) fetch('/api/groups/delete', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({id}) }).then(updateUI);
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

@app.route('/api/groups/add', methods=['POST'])
def add_group():
    state.control.add_group(request.json['name'])
    return jsonify({"status": "success"})

@app.route('/api/groups/delete', methods=['POST'])
def delete_group():
    state.control.delete_group(request.json['id'])
    return jsonify({"status": "success"})

@app.route('/api/groups/update', methods=['POST'])
def update_group():
    data = request.json
    state.control.update_group(data['id'], data['settings'])
    return jsonify({"status": "success"})

@app.route('/api/data')
def get_data():
    return jsonify(state.current_data)

if __name__ == '__main__':
    t = threading.Thread(target=control_loop)
    t.daemon = True
    t.start()
    app.run(host='0.0.0.0', port=5000)
