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
        <title>Berry_WHAT Expert 제어 시스템</title>
        <style>
            body { font-family: 'Segoe UI', sans-serif; margin: 0; padding: 20px; background-color: #eceff1; color: #333; }
            .container { max-width: 1400px; margin: auto; }
            .header { display: flex; justify-content: space-between; align-items: center; background: #2e7d32; color: white; padding: 15px 25px; border-radius: 12px; margin-bottom: 20px; }
            .card { background: white; padding: 20px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); margin-bottom: 20px; }
            
            .monitor-grid { display: grid; grid-template-columns: repeat(6, 1fr); gap: 10px; margin-bottom: 20px; }
            .monitor-box { background: #fff; padding: 15px; border-radius: 8px; text-align: center; border: 1px solid #cfd8dc; }
            .monitor-box span { font-size: 12px; color: #546e7a; font-weight: bold; }
            .monitor-box b { font-size: 24px; color: #2e7d32; display: block; margin-top: 5px; }
            
            .state-banner { padding: 15px; border-radius: 8px; font-weight: bold; text-align: center; margin-bottom: 20px; font-size: 18px; text-transform: uppercase; }
            .state-standby { background: #cfd8dc; color: #455a64; }
            .state-active { background: #e8f5e9; color: #2e7d32; border: 2px solid #2e7d32; }
            .state-alarm { background: #ffebee; color: #c62828; border: 2px solid #c62828; }

            .main-layout { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 20px; }
            .group-card { border: 1px solid #e0e0e0; padding: 15px; border-radius: 10px; margin-bottom: 15px; background: #fdfdfd; position: relative; }
            
            .tank-bar { height: 18px; background: #e0e0e0; border-radius: 9px; overflow: hidden; margin-top: 5px; border: 1px solid #ccc; }
            .tank-fill { height: 100%; background: #43a047; transition: 0.5s; width: 0%; }
            .input-field { width: 65px; padding: 6px; border: 1px solid #cfd8dc; border-radius: 4px; font-size: 12px; }
            .label { font-size: 11px; color: #546e7a; font-weight: bold; }
            .btn { padding: 10px 20px; border-radius: 6px; border: none; font-weight: bold; cursor: pointer; transition: 0.3s; }
            .btn-primary { background: #2e7d32; color: white; }
            .btn-primary:hover { background: #1b5e20; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1 style="margin:0;">🌿 Berry_WHAT Expert System</h1>
                <div id="conn-info">상태: <b id="status-text">--</b> | 모드: <b id="mode-text">--</b></div>
            </div>

            <div id="system-state" class="state-banner state-standby">SYSTEM STANDBY</div>

            <div class="monitor-grid">
                <div class="monitor-box"><span>현재 온도</span><b id="temp">--</b></div>
                <div class="monitor-box"><span>VPD (kPa)</span><b id="vpd">--</b></div>
                <div class="monitor-box"><span>일사 적산</span><b id="solar">--</b></div>
                <div class="monitor-box"><span>토양 수분</span><b id="moist">--</b></div>
                <div class="monitor-box"><span>양액 EC</span><b id="ec">--</b></div>
                <div class="monitor-box"><span>양액 pH</span><b id="ph">--</b></div>
            </div>

            <div class="main-layout">
                <div>
                    <div class="card">
                        <h2>🌡️ 대기 & VPD 제어</h2>
                        <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px;">
                            <div><label class="label">목표 온도</label><br><input id="target_temp" class="input-field"></div>
                            <div><label class="label">데드밴드</label><br><input id="temp_deadband" class="input-field"></div>
                            <div><label class="label">최소 VPD</label><br><input id="vpd_min" class="input-field"></div>
                            <div><label class="label">최대 VPD</label><br><input id="vpd_max" class="input-field"></div>
                        </div>
                        <button class="btn btn-primary" style="width:100%; margin-top:15px;" onclick="saveAir()">설정 저장</button>
                    </div>
                    <div class="card">
                        <h2>⚙️ 장치 작동 상태</h2>
                        <div id="actuator-list"></div>
                    </div>
                </div>

                <div class="card">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <h2>💧 관수 구역 (Valve Groups)</h2>
                        <button class="btn btn-primary" onclick="addGroup()" style="padding:5px 10px;">+ 추가</button>
                    </div>
                    <div id="group-container"></div>
                </div>

                <div class="card">
                    <h2>🧪 양액 탱크 레벨</h2>
                    <div style="margin-bottom:20px;"><label class="label">A액 탱크 (영양액)</label> <span id="tank_a_val">0%</span><div class="tank-bar"><div id="tank_a_bar" class="tank-fill"></div></div></div>
                    <div style="margin-bottom:20px;"><label class="label">B액 탱크 (영양액)</label> <span id="tank_b_val">0%</span><div class="tank-bar"><div id="tank_b_bar" class="tank-fill"></div></div></div>
                    <div style="margin-bottom:20px;"><label class="label">산성 탱크 (pH 조절)</label> <span id="tank_acid_val">0%</span><div class="tank-bar"><div id="tank_acid_bar" class="tank-fill" style="background:#f44336;"></div></div></div>
                    <button class="btn" style="background:#546e7a; color:white; width:100%;">Tanks Manual Refill</button>
                </div>
            </div>
        </div>
        <script>
            function updateUI() {
                fetch('/api/data').then(r => r.json()).then(data => {
                    document.getElementById('temp').innerText = data.temp + '°C';
                    document.getElementById('vpd').innerText = data.vpd;
                    document.getElementById('solar').innerText = data.solar_accumulation + ' J';
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
                    const stateEl = document.getElementById('system-state');
                    stateEl.innerText = 'SYSTEM STATE: ' + status.actuators.state;
                    stateEl.className = 'state-banner ' + (status.actuators.state === 'ALARM' ? 'state-alarm' : (status.actuators.state === 'STANDBY' ? 'state-standby' : 'state-active'));

                    let actHtml = '';
                    for (const [key, val] of Object.entries(status.actuators)) {
                        if(key === 'state') continue;
                        actHtml += '<div style="display:flex;justify-content:space-between;font-size:13px;padding:6px 0;border-bottom:1px solid #eee;"><span>' + key + '</span><b>' + val + '</b></div>';
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
                        const active = g.status !== 'Ready' && g.status !== 'Disabled';
                        html += '<div class="group-card">' +
                                '<span style="position:absolute;top:10px;right:10px;font-size:10px;padding:2px 8px;border-radius:10px;background:' + (active ? '#e8f5e9' : '#eceff1') + ';color:' + (active ? '#2e7d32' : '#546e7a') + '">' + g.status + '</span>' +
                                '<b>' + g.name + '</b>' +
                                '<div style="display:grid; grid-template-columns:1fr 1fr; gap:5px; margin-top:10px; font-size:11px;">' +
                                '<div><label class="label">시작</label><input class="input-field" type="time" style="width:100%" id="start-' + g.id + '" value="' + g.start_time + '"></div>' +
                                '<div><label class="label">종료</label><input class="input-field" type="time" style="width:100%" id="end-' + g.id + '" value="' + g.end_time + '"></div>' +
                                '<div><label class="label">목표EC</label><input class="input-field" id="ec-' + g.id + '" value="' + g.target_ec + '"></div>' +
                                '<div><label class="label">일사임계</label><input class="input-field" id="solar-' + g.id + '" value="' + g.solar_threshold + '"></div>' +
                                '</div>' +
                                '<button class="btn btn-primary" style="margin-top:10px; width:100%; font-size:11px; padding:6px;" onclick="saveGroup(' + g.id + ')">설정 저장</button>' +
                                '</div>';
                    });
                    document.getElementById('group-container').innerHTML = html;
                });
            }
            function saveAir() {
                const s = { target_temp: parseFloat(document.getElementById('target_temp').value), temp_deadband: parseFloat(document.getElementById('temp_deadband').value), vpd_min: parseFloat(document.getElementById('vpd_min').value), vpd_max: parseFloat(document.getElementById('vpd_max').value) };
                fetch('/api/air/update', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(s) }).then(() => alert('환경 설정 저장됨'));
            }
            function saveGroup(id) {
                const s = { start_time: document.getElementById('start-' + id).value, end_time: document.getElementById('end-' + id).value, target_ec: parseFloat(document.getElementById('ec-' + id).value), solar_threshold: parseFloat(document.getElementById('solar-' + id).value) };
                fetch('/api/groups/update', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({id, settings: s}) }).then(() => alert('구역 설정 저장됨'));
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
