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
        data = state.collector.collect_signals(actuator_status=state.control.get_actuator_status())
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
        <title>Berry_WHAT 통합 제어</title>
        <style>
            body { font-family: 'Malgun Gothic', sans-serif; margin: 0; padding: 20px; background-color: #f4f7f4; color: #333; }
            .container { max-width: 1400px; margin: auto; }
            .card { background: white; padding: 20px; border-radius: 12px; box-shadow: 0 4px 10px rgba(0,0,0,0.05); margin-bottom: 20px; }
            .grid-6 { display: grid; grid-template-columns: repeat(6, 1fr); gap: 10px; margin-bottom: 20px; }
            .monitor-box { background: #fff; padding: 15px; border-radius: 8px; text-align: center; border: 1px solid #d0e0d0; }
            .monitor-box b { font-size: 22px; color: #2e7d32; display: block; }
            .main-layout { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 20px; }
            .group-card { border: 1px solid #eee; padding: 15px; border-radius: 10px; margin-bottom: 15px; background: #fafafa; position: relative; }
            .tank-bar { height: 18px; background: #eee; border-radius: 10px; overflow: hidden; margin-top: 5px; }
            .tank-fill { height: 100%; background: #4caf50; transition: 0.5s; width: 0%; }
            .input-field { width: 65px; padding: 5px; border: 1px solid #ddd; border-radius: 4px; font-size: 12px; }
            .label { font-size: 11px; color: #666; font-weight: bold; }
            .btn { padding: 8px 15px; border-radius: 4px; border: none; font-weight: bold; cursor: pointer; }
            .status-tag { position: absolute; top: 12px; right: 12px; font-size: 10px; padding: 2px 8px; border-radius: 10px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🌿 Berry_WHAT 통합 제어 시스템</h1>
            <div class="grid-6">
                <div class="monitor-box"><span>온도</span><b id="temp">--</b></div>
                <div class="monitor-box"><span>VPD</span><b id="vpd">--</b></div>
                <div class="monitor-box"><span>일사적산</span><b id="solar">--</b></div>
                <div class="monitor-box"><span>수분</span><b id="moist">--</b></div>
                <div class="monitor-box"><span>EC</span><b id="ec">--</b></div>
                <div class="monitor-box"><span>pH</span><b id="ph">--</b></div>
            </div>
            <div class="main-layout">
                <div>
                    <div class="card">
                        <h2>🌡️ 대기 환경 설정</h2>
                        <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px;">
                            <div><label class="label">목표온도</label><br><input id="target_temp" class="input-field"></div>
                            <div><label class="label">데드밴드</label><br><input id="temp_deadband" class="input-field"></div>
                            <div><label class="label">최소VPD</label><br><input id="vpd_min" class="input-field"></div>
                            <div><label class="label">최대VPD</label><br><input id="vpd_max" class="input-field"></div>
                        </div>
                        <button class="btn" style="width:100%; margin-top:15px; background:#4caf50; color:white;" onclick="saveAir()">대기설정 적용</button>
                    </div>
                    <div class="card">
                        <h2>⚙️ 장치 상태</h2>
                        <div id="actuator-list"></div>
                    </div>
                </div>
                <div class="card">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <h2>💧 관수 구역 관리</h2>
                        <button class="btn" onclick="addGroup()" style="background:#2196f3; color:white;">+ 추가</button>
                    </div>
                    <div id="group-container"></div>
                </div>
                <div class="card">
                    <h2>🧪 양액 탱크 모니터링</h2>
                    <div style="margin-bottom:20px;"><label class="label">A액 탱크</label> <span id="tank_a_val">0%</span><div class="tank-bar"><div id="tank_a_bar" class="tank-fill"></div></div></div>
                    <div style="margin-bottom:20px;"><label class="label">B액 탱크</label> <span id="tank_b_val">0%</span><div class="tank-bar"><div id="tank_b_bar" class="tank-fill"></div></div></div>
                    <div style="margin-bottom:20px;"><label class="label">산성(pH) 탱크</label> <span id="tank_acid_val">0%</span><div class="tank-bar"><div id="tank_acid_bar" class="tank-fill" style="background:#f44336;"></div></div></div>
                    <button class="btn" style="background:#666; color:white; width:100%;">탱크 보충 (Manual)</button>
                </div>
            </div>
        </div>
        <script>
            function updateUI() {
                fetch('/api/data').then(r => r.json()).then(data => {
                    document.getElementById('temp').innerText = data.temp + '°C';
                    document.getElementById('vpd').innerText = data.vpd + ' kPa';
                    document.getElementById('solar').innerText = data.solar_accumulation;
                    document.getElementById('moist').innerText = data.moisture + '%';
                    document.getElementById('ec').innerText = data.ec;
                    document.getElementById('ph').innerText = data.ph;
                    document.getElementById('tank_a_val').innerText = data.tank_a + '%';
                    document.getElementById('tank_a_bar').style.width = data.tank_a + '%';
                    document.getElementById('tank_b_val').innerText = data.tank_b + '%';
                    document.getElementById('tank_b_bar').style.width = data.tank_b + '%';
                    document.getElementById('tank_acid_val').innerText = data.tank_acid + '%';
                    document.getElementById('tank_acid_bar').style.width = data.tank_acid + '%';
                });
                fetch('/api/status').then(r => r.json()).then(status => {
                    let actHtml = '';
                    for (const [key, val] of Object.entries(status.actuators)) {
                        actHtml += '<div style="display:flex;justify-content:space-between;font-size:12px;padding:4px 0;border-bottom:1px solid #eee;"><span>' + key + '</span><b>' + val + '</b></div>';
                    }
                    document.getElementById('actuator-list').innerHTML = actHtml;
                    if(!document.activeElement.classList.contains('input-field')) {
                        document.getElementById('target_temp').value = status.air.target_temp;
                        document.getElementById('temp_deadband').value = status.air.temp_deadband;
                        document.getElementById('vpd_min').value = status.air.vpd_min;
                        document.getElementById('vpd_max').value = status.air.vpd_max;
                    }
                });
                fetch('/api/groups').then(r => r.json()).then(groups => {
                    let html = '';
                    groups.forEach(g => {
                        html += '<div class="group-card">' +
                                '<span class="status-tag" style="background:' + (g.status.includes('Water') ? '#e8f5e9' : '#e3f2fd') + '; color:' + (g.status.includes('Water') ? '#2e7d32' : '#1976d2') + '">' + g.status + '</span>' +
                                '<b>' + g.name + '</b>' +
                                '<div style="display:grid; grid-template-columns:1fr 1fr; gap:5px; margin-top:10px;">' +
                                '<div><label class="label">시작</label><input class="input-field" type="time" style="width:100%" id="start-' + g.id + '" value="' + g.start_time + '"></div>' +
                                '<div><label class="label">종료</label><input class="input-field" type="time" style="width:100%" id="end-' + g.id + '" value="' + g.end_time + '"></div>' +
                                '<div><label class="label">목표EC</label><input class="input-field" id="ec-' + g.id + '" value="' + g.target_ec + '"></div>' +
                                '<div><label class="label">일사임계</label><input class="input-field" id="solar-' + g.id + '" value="' + g.solar_threshold + '"></div>' +
                                '</div>' +
                                '<button class="btn" style="margin-top:10px; width:100%; font-size:11px; background:#4caf50; color:white;" onclick="saveGroup(' + g.id + ')">저장</button>' +
                                '</div>';
                    });
                    document.getElementById('group-container').innerHTML = html;
                });
            }
            function saveAir() {
                const s = { target_temp: parseFloat(document.getElementById('target_temp').value), temp_deadband: parseFloat(document.getElementById('temp_deadband').value), vpd_min: parseFloat(document.getElementById('vpd_min').value), vpd_max: parseFloat(document.getElementById('vpd_max').value) };
                fetch('/api/air/update', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(s) }).then(() => alert('대기설정 저장됨'));
            }
            function saveGroup(id) {
                const s = { start_time: document.getElementById('start-' + id).value, end_time: document.getElementById('end-' + id).value, target_ec: parseFloat(document.getElementById('ec-' + id).value), solar_threshold: parseFloat(document.getElementById('solar-' + id).value) };
                fetch('/api/groups/update', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({id, settings: s}) }).then(() => alert('구역설정 저장됨'));
            }
            function addGroup() {
                const name = prompt("구역 이름:");
                if(name) fetch('/api/groups/add', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({name}) }).then(updateUI);
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
        "air": {"target_temp": state.control.target_temp, "temp_deadband": state.control.temp_deadband, "vpd_min": state.control.target_vpd_min, "vpd_max": state.control.target_vpd_max}
    })

@app.route('/api/air/update', methods=['POST'])
def update_air():
    data = request.json
    state.control.target_temp = data['target_temp']
    state.control.temp_deadband = data['temp_deadband']
    state.control.target_vpd_min = data['vpd_min']
    state.control.target_vpd_max = data['vpd_max']
    state.db.set_config("target_temp", data['target_temp'])
    state.db.set_config("temp_deadband", data['temp_deadband'])
    state.db.set_config("target_vpd_min", data['vpd_min'])
    state.db.set_config("target_vpd_max", data['vpd_max'])
    return jsonify({"status": "success"})

@app.route('/api/groups')
def get_groups(): return jsonify(state.control.get_irrigation_status())

@app.route('/api/groups/add', methods=['POST'])
def add_group():
    state.control.add_group(request.json['name'])
    return jsonify({"status": "success"})

@app.route('/api/groups/update', methods=['POST'])
def update_group():
    data = request.json
    state.control.update_group(data['id'], data['settings'])
    return jsonify({"status": "success"})

@app.route('/api/data')
def get_data(): return jsonify(state.current_data)

if __name__ == '__main__':
    t = threading.Thread(target=control_loop)
    t.daemon = True
    t.start()
    app.run(host='0.0.0.0', port=5000)
