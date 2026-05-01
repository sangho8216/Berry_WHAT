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
        <title>Berry_WHAT 멀티구역 제어 시스템</title>
        <style>
            body { font-family: 'Malgun Gothic', sans-serif; margin: 40px; background-color: #f4f7f4; }
            .container { max-width: 1000px; margin: auto; }
            .card { background: white; padding: 20px; border-radius: 12px; box-shadow: 0 2px 10px rgba(0,0,0,0.05); margin-bottom: 20px; }
            .group-card { border: 1px solid #eee; padding: 15px; border-radius: 8px; position: relative; margin-bottom: 15px; }
            .status-tag { position: absolute; top: 15px; right: 15px; padding: 4px 12px; border-radius: 20px; font-size: 11px; font-weight: bold; }
            .tag-ready { background: #e3f2fd; color: #1976d2; }
            .tag-watering { background: #e8f5e9; color: #2e7d32; animation: blink 1s infinite; }
            .tag-disabled { background: #f5f5f5; color: #9e9e9e; }
            @keyframes blink { 50% { opacity: 0.5; } }
            .action-btn { cursor: pointer; border: none; background: none; color: #666; font-size: 12px; margin-left: 10px; }
            .add-btn { background: #4caf50; color: white; padding: 10px 20px; border-radius: 5px; border: none; cursor: pointer; font-weight: bold; }
            .grid-env { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-bottom: 20px; }
            .env-box { background: #fff; padding: 10px; border-radius: 8px; text-align: center; border: 1px solid #e0eee0; }
            .val { font-size: 18px; font-weight: bold; display: block; }
            .input-edit { border: 1px solid #ddd; padding: 4px; border-radius: 3px; font-size: 16px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🌿 구역별 정밀 관수 관리</h1>
            
            <div class="grid-env">
                <div class="env-box"><span>내부 온도</span><b id="temp" class="val">--</b></div>
                <div class="env-box"><span>포차(VPD)</span><b id="vpd" class="val">--</b></div>
                <div class="env-box"><span>일사적산</span><b id="solar" class="val">--</b></div>
                <div class="env-box"><span>토양수분</span><b id="moist" class="val">--</b></div>
            </div>

            <div class="card">
                <div style="display:flex; justify-content:space-between; margin-bottom:20px;">
                    <h2>관수 구역 설정</h2>
                    <button class="add-btn" onclick="addGroup()">+ 새 구역 추가</button>
                </div>
                <div id="group-container"></div>
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
                        html += '<div class="group-card">' +
                                '<span class="status-tag ' + tagClass + '">' + g.status + '</span>' +
                                '<input class="input-edit" id="name-' + g.id + '" value="' + g.name + '" onblur="updateName(' + g.id + ', this.value)">' +
                                '<div style="margin: 10px 0;">' +
                                '활성화 <input type="checkbox" ' + (g.enabled ? 'checked' : '') + ' onchange="toggleGroup(' + g.id + ', this.checked)">' +
                                '<button class="action-btn" onclick="deleteGroup(' + g.id + ')">🗑 삭제</button>' +
                                '</div>' +
                                '<div style="font-size: 12px; color: #666;">일사: ' + g.solar_threshold + 'J | 수분: ' + g.min_moisture + '% | 지속: ' + g.duration + '초</div>' +
                                '</div>';
                    });
                    container.innerHTML = html;
                });
            }

            function addGroup() {
                const name = prompt("새 구역 이름을 입력하세요:");
                if(name) fetch('/api/groups/add', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({name}) }).then(updateUI);
            }
            function deleteGroup(id) {
                if(confirm("정말 삭제하시겠습니까?")) fetch('/api/groups/delete', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({id}) }).then(updateUI);
            }
            function updateName(id, name) {
                fetch('/api/groups/update', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({id, settings: {name}}) });
            }
            function toggleGroup(id, enabled) {
                fetch('/api/groups/update', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({id, settings: {enabled: enabled ? 1 : 0}}) });
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

@app.route('/api/history')
def get_history():
    return jsonify(state.db.get_history(20))

if __name__ == '__main__':
    t = threading.Thread(target=control_loop)
    t.daemon = True
    t.start()
    app.run(host='0.0.0.0', port=5000)
