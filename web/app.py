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
        <title>Berry_WHAT 스킬 통합 제어 시스템</title>
        <style>
            body { font-family: 'Malgun Gothic', sans-serif; margin: 0; padding: 20px; background-color: #f0f2f0; color: #333; }
            .container { max-width: 1300px; margin: auto; }
            .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
            .card { background: white; padding: 20px; border-radius: 12px; box-shadow: 0 4px 10px rgba(0,0,0,0.05); margin-bottom: 20px; }
            .monitor-grid { display: grid; grid-template-columns: repeat(6, 1fr); gap: 10px; margin-bottom: 20px; }
            .monitor-box { background: #fff; padding: 15px; border-radius: 8px; text-align: center; border: 1px solid #d0e0d0; }
            .monitor-box b { font-size: 22px; color: #2e7d32; display: block; margin-top: 5px; }
            .middle-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
            .group-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 20px; }
            .group-card { border: 1px solid #eee; padding: 15px; border-radius: 10px; position: relative; background: #fafafa; }
            .status-tag { position: absolute; top: 15px; right: 15px; padding: 3px 10px; border-radius: 15px; font-size: 11px; font-weight: bold; }
            .tag-watering { background: #e8f5e9; color: #2e7d32; animation: blink 1s infinite; }
            .tag-ready { background: #e3f2fd; color: #1976d2; }
            @keyframes blink { 50% { opacity: 0.5; } }
            .input-field { width: 65px; padding: 5px; border: 1px solid #ddd; border-radius: 4px; }
            .label { font-size: 11px; color: #666; font-weight: bold; }
            button { cursor: pointer; border-radius: 4px; font-weight: bold; transition: 0.2s; }
            .btn-save { background: #4caf50; color: white; border: none; padding: 8px 15px; }
            .btn-add { background: #2196f3; color: white; border: none; padding: 10px 20px; }
            .actuator-item { display: flex; justify-content: space-between; padding: 7px 0; border-bottom: 1px solid #eee; font-size: 14px; }
            .act-on { color: #2196f3; font-weight: bold; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🌿 Berry_WHAT 스킬 통합 제어</h1>
                <div id="conn-info">상태: <b id="status-text">--</b> | 모드: <b id="mode-text">--</b></div>
            </div>
            <div class="monitor-grid">
                <div class="monitor-box"><span>온도</span><b id="temp">--</b></div>
                <div class="monitor-box"><span>습도</span><b id="hum">--</b></div>
                <div class="monitor-box"><span>VPD</span><b id="vpd">--</b></div>
                <div class="monitor-box"><span>일사적산</span><b id="solar">--</b></div>
                <div class="monitor-box"><span>EC</span><b id="ec">--</b></div>
                <div class="monitor-box"><span>pH</span><b id="ph">--</b></div>
            </div>
            <div class="middle-grid">
                <div class="card">
                    <h2>🌡️ 대기 및 VPD 환경 설정 (Skill 기준)</h2>
                    <div style="display:grid; grid-template-columns: 1fr 1fr; gap:15px;">
                        <div><label class="label">목표 온도 (°C)</label><br><input type="number" id="target_temp" class="input-field" step="0.5"></div>
                        <div><label class="label">온도 편차</label><br><input type="number" id="temp_deadband" class="input-field" step="0.1"></div>
                        <div><label class="label">최소 VPD (kPa)</label><br><input type="number" id="target_vpd_min" class="input-field" step="0.1"></div>
                        <div><label class="label">최대 VPD (kPa)</label><br><input type="number" id="target_vpd_max" class="input-field" step="0.1"></div>
                    </div>
                    <button class="btn-save" style="margin-top:15px; width:100%;" onclick="saveAirSettings()">환경 제어 설정 적용</button>
                </div>
                <div class="card">
                    <h2>⚙️ 구동 장치 실시간 상태</h2>
                    <div id="actuator-list"></div>
                </div>
            </div>
            <div class="card">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:15px;">
                    <h2>💧 관수/양액 구역별 세부 설정</h2>
                    <button class="btn-add" onclick="addGroup()">+ 새 구역 추가</button>
                </div>
                <div class="group-grid" id="group-container"></div>
            </div>
        </div>
        <script>
            function updateUI() {
                fetch('/api/data').then(r => r.json()).then(data => {
                    document.getElementById('status-text').innerText = data.status || 'Disconnected';
                    document.getElementById('temp').innerText = (data.temp || 0) + '°C';
                    document.getElementById('hum').innerText = (data.humidity || 0) + '%';
                    document.getElementById('vpd').innerText = (data.vpd || 0) + ' kPa';
                    document.getElementById('solar').innerText = data.solar_accumulation || 0;
                    document.getElementById('ec').innerText = (data.ec || 0);
                    document.getElementById('ph').innerText = (data.ph || 0);
                });
                fetch('/api/status').then(r => r.json()).then(status => {
                    document.getElementById('mode-text').innerText = status.mode;
                    let actHtml = '';
                    for (const [key, val] of Object.entries(status.actuators)) {
                        const activeClass = (val !== 'Off' && val !== 'Closed') ? 'act-on' : '';
                        actHtml += '<div class="actuator-item"><span>' + key + '</span><b class="' + activeClass + '">' + val + '</b></div>';
                    }
                    document.getElementById('actuator-list').innerHTML = actHtml;
                    if(!document.activeElement.classList.contains('input-field')) {
                        document.getElementById('target_temp').value = status.air_settings.target_temp;
                        document.getElementById('temp_deadband').value = status.air_settings.temp_deadband;
                        document.getElementById('target_vpd_min').value = status.air_settings.target_vpd_min;
                        document.getElementById('target_vpd_max').value = status.air_settings.target_vpd_max;
                    }
                });
                fetch('/api/groups').then(r => r.json()).then(groups => {
                    const container = document.getElementById('group-container');
                    let html = '';
                    groups.forEach(g => {
                        const tagClass = g.status.toLowerCase().includes('water') ? 'tag-watering' : 'tag-ready';
                        html += '<div class="group-card">' +
                                '<span class="status-tag ' + tagClass + '">' + g.status + '</span>' +
                                '<h3>' + g.name + '</h3>' +
                                '<div style="display:grid; grid-template-columns: 1fr 1fr; gap:8px;">' +
                                '<div><label class="label">활성화</label> <input type="checkbox" ' + (g.enabled ? 'checked' : '') + ' onchange="toggleGroup(' + g.id + ', this.checked)"></div>' +
                                '<div><label class="label">시작/종료</label><br><span style="font-size:11px">' + g.start_time + '~' + g.end_time + '</span></div>' +
                                '<div><label class="label">목표 EC/pH</label><br><input class="input-field" id="ec-' + g.id + '" value="' + g.target_ec + '"> <input class="input-field" id="ph-' + g.id + '" value="' + g.target_ph + '"></div>' +
                                '<div><label class="label">일사/수분임계</label><br><input class="input-field" id="solar-' + g.id + '" value="' + g.solar_threshold + '"> <input class="input-field" id="moist-' + g.id + '" value="' + g.min_moisture + '"></div>' +
                                '</div>' +
                                '<div style="margin-top:12px; display:flex; justify-content:space-between;">' +
                                '<button class="btn-save" onclick="saveGroup(' + g.id + ')">저장</button>' +
                                '<button onclick="deleteGroup(' + g.id + ')" style="color:red; background:none; border:none; cursor:pointer; font-size:11px;">삭제</button>' +
                                '</div></div>';
                    });
                    container.innerHTML = html;
                });
            }
            function saveAirSettings() {
                const settings = {
                    target_temp: parseFloat(document.getElementById('target_temp').value),
                    temp_deadband: parseFloat(document.getElementById('temp_deadband').value),
                    target_vpd_min: parseFloat(document.getElementById('target_vpd_min').value),
                    target_vpd_max: parseFloat(document.getElementById('target_vpd_max').value)
                };
                fetch('/api/air/update', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(settings) })
                .then(() => alert('스킬 기반 환경 설정이 적용되었습니다.'));
            }
            function saveGroup(id) {
                const settings = {
                    target_ec: parseFloat(document.getElementById('ec-' + id).value),
                    target_ph: parseFloat(document.getElementById('ph-' + id).value),
                    solar_threshold: parseFloat(document.getElementById('solar-' + id).value),
                    min_moisture: parseFloat(document.getElementById('moist-' + id).value)
                };
                fetch('/api/groups/update', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({id, settings}) })
                .then(() => alert('구역 설정 저장됨'));
            }
            function addGroup() {
                const name = prompt("새 구역 이름:");
                if(name) fetch('/api/groups/add', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({name}) }).then(updateUI);
            }
            function deleteGroup(id) {
                if(confirm("삭제?")) fetch('/api/groups/delete', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({id}) }).then(updateUI);
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

@app.route('/api/status')
def get_status():
    return jsonify({
        "mode": state.mode,
        "actuators": state.control.get_actuator_status(),
        "air_settings": {
            "target_temp": state.control.target_temp,
            "temp_deadband": state.control.temp_deadband,
            "target_vpd_min": state.control.target_vpd_min,
            "target_vpd_max": state.control.target_vpd_max
        }
    })

@app.route('/api/air/update', methods=['POST'])
def update_air():
    data = request.json
    state.control.target_temp = data['target_temp']
    state.control.temp_deadband = data['temp_deadband']
    state.control.target_vpd_min = data['target_vpd_min']
    state.control.target_vpd_max = data['target_vpd_max']
    return jsonify({"status": "success"})

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
