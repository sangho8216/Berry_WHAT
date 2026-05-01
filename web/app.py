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
        <title>Berry_WHAT Expert 제어</title>
        <style>
            body { font-family: 'Segoe UI', sans-serif; margin: 0; padding: 20px; background-color: #eceff1; }
            .container { max-width: 1400px; margin: auto; }
            .card { background: white; padding: 20px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); margin-bottom: 20px; }
            .grid-6 { display: grid; grid-template-columns: repeat(6, 1fr); gap: 10px; margin-bottom: 20px; }
            .monitor-box { background: #fff; padding: 15px; border-radius: 8px; text-align: center; border: 1px solid #cfd8dc; }
            .monitor-box b { font-size: 22px; color: #2e7d32; display: block; }
            .state-banner { padding: 12px; border-radius: 8px; font-weight: bold; text-align: center; margin-bottom: 20px; font-size: 16px; }
            .state-standby { background: #cfd8dc; color: #455a64; }
            .state-active { background: #e8f5e9; color: #2e7d32; border: 2px solid #2e7d32; }
            .main-layout { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 20px; }
            .group-card { border: 1px solid #e0e0e0; padding: 15px; border-radius: 10px; margin-bottom: 15px; background: #fdfdfd; position: relative; }
            .input-field { width: 65px; padding: 5px; border: 1px solid #cfd8dc; border-radius: 4px; font-size: 12px; }
            .label { font-size: 11px; color: #546e7a; font-weight: bold; }
            .btn { padding: 8px 15px; border-radius: 6px; border: none; font-weight: bold; cursor: pointer; }
            .btn-primary { background: #2e7d32; color: white; }
            .btn-detail { background: #546e7a; color: white; font-size: 11px; padding: 4px 8px; }
            .modal { display: none; position: fixed; z-index: 100; left: 0; top: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); }
            .modal-content { background: white; margin: 10% auto; padding: 25px; border-radius: 15px; width: 400px; }
            .tank-bar { height: 15px; background: #e0e0e0; border-radius: 7px; overflow: hidden; margin-top: 5px; }
            .tank-fill { height: 100%; background: #43a047; transition: 0.5s; width: 0%; }
        </style>
    </head>
    <body>
        <div class="container">
            <div id="system-state" class="state-banner state-standby">SYSTEM STANDBY</div>
            <div class="grid-6">
                <div class="monitor-box"><span>온도</span><b id="temp">--</b></div>
                <div class="monitor-box"><span>VPD</span><b id="vpd">--</b></div>
                <div class="monitor-box"><span>일사적산</span><b id="solar">--</b></div>
                <div class="monitor-box"><span>토양수분</span><b id="moist">--</b></div>
                <div class="monitor-box"><span>EC</span><b id="ec">--</b></div>
                <div class="monitor-box"><span>pH</span><b id="ph">--</b></div>
            </div>
            <div class="main-layout">
                <div>
                    <div class="card">
                        <h2>🌡️ 환경 설정</h2>
                        <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px;">
                            <div><label class="label">목표온도</label><br><input id="target_temp" class="input-field"></div>
                            <div><label class="label">데드밴드</label><br><input id="temp_deadband" class="input-field"></div>
                        </div>
                        <button class="btn btn-primary" style="width:100%; margin-top:15px;" onclick="saveAir()">설정 적용</button>
                    </div>
                    <div class="card">
                        <h2>⚙️ 장치 상태</h2>
                        <div id="actuator-list"></div>
                    </div>
                </div>
                <div class="card">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <h2>💧 관수 구역</h2>
                        <button class="btn btn-primary" onclick="addGroup()">+ 추가</button>
                    </div>
                    <div id="group-container"></div>
                </div>
                <div class="card">
                    <h2>🧪 양액 탱크</h2>
                    <div style="margin-bottom:15px;"><label class="label">A액 탱크</label> <span id="tank_a_val">0%</span><div class="tank-bar"><div id="tank_a_bar" class="tank-fill"></div></div></div>
                    <div style="margin-bottom:15px;"><label class="label">B액 탱크</label> <span id="tank_b_val">0%</span><div class="tank-bar"><div id="tank_b_bar" class="tank-fill"></div></div></div>
                    <div style="margin-bottom:15px;"><label class="label">산성 탱크</label> <span id="tank_acid_val">0%</span><div class="tank-bar"><div id="tank_acid_bar" class="tank-fill" style="background:#f44336;"></div></div></div>
                </div>
            </div>
        </div>
        <div id="detailModal" class="modal">
            <div class="modal-content">
                <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #eee; padding-bottom:10px; margin-bottom:15px;">
                    <h2 id="modal-title" style="margin:0;">세부 설정</h2>
                    <span style="cursor:pointer; font-size:24px;" onclick="closeModal()">&times;</span>
                </div>
                <input type="hidden" id="modal-group-id">
                <div style="display:grid; grid-template-columns:1fr 1fr; gap:15px;">
                    <div><label class="label">시작 시간</label><input type="time" id="m-start" class="input-field" style="width:100%"></div>
                    <div><label class="label">종료 시간</label><input type="time" id="m-end" class="input-field" style="width:100%"></div>
                    <div><label class="label">최소일사(W)</label><input type="number" id="m-min-rad" class="input-field"></div>
                    <div><label class="label">최대휴지(분)</label><input type="number" id="m-fixed-int" class="input-field"></div>
                    <div><label class="label">후수세척(초)</label><input type="number" id="m-rinse" class="input-field"></div>
                    <div><label class="label">관수간격(분)</label><input type="number" id="m-interval" class="input-field"></div>
                </div>
                <button class="btn btn-primary" style="width:100%; margin-top:20px;" onclick="saveModalSettings()">세부 설정 저장</button>
            </div>
        </div>
        <script>
            let currentGroups = [];
            function updateUI() {
                fetch('/api/data').then(r => r.json()).then(data => {
                    document.getElementById('temp').innerText = data.temp + '°C';
                    document.getElementById('vpd').innerText = data.vpd;
                    document.getElementById('solar').innerText = data.solar_accumulation;
                    document.getElementById('moist').innerText = data.moisture + '%';
                    document.getElementById('ec').innerText = data.ec;
                    document.getElementById('ph').innerText = data.ph;
                    document.getElementById('tank_a_bar').style.width = data.tank_a + '%';
                    document.getElementById('tank_b_bar').style.width = data.tank_b + '%';
                    document.getElementById('tank_acid_bar').style.width = data.tank_acid + '%';
                });
                fetch('/api/status').then(r => r.json()).then(status => {
                    const stateEl = document.getElementById('system-state');
                    stateEl.innerText = 'SYSTEM STATE: ' + status.actuators.state;
                    stateEl.className = 'state-banner ' + (status.actuators.state === 'STANDBY' ? 'state-standby' : 'state-active');
                    let actHtml = '';
                    for (const [key, val] of Object.entries(status.actuators)) {
                        if(key === 'state') continue;
                        actHtml += '<div style="display:flex;justify-content:space-between;font-size:12px;padding:4px 0;border-bottom:1px solid #eee;"><span>' + key + '</span><b>' + val + '</b></div>';
                    }
                    document.getElementById('actuator-list').innerHTML = actHtml;
                    if(!document.activeElement.classList.contains('input-field')) {
                        document.getElementById('target_temp').value = status.air.target_temp;
                        document.getElementById('temp_deadband').value = status.air.temp_deadband;
                    }
                });
                fetch('/api/groups').then(r => r.json()).then(groups => {
                    currentGroups = groups;
                    let html = '';
                    groups.forEach(g => {
                        html += '<div class="group-card"><span style="position:absolute;top:10px;right:10px;font-size:9px;padding:2px 6px;border-radius:10px;background:#eceff1;">' + g.status + '</span><b>' + g.name + '</b><div style="display:grid; grid-template-columns:1fr 1fr; gap:5px; margin-top:10px;"><div><label class="label">목표EC</label><input class="input-field" id="ec-' + g.id + '" value="' + g.target_ec + '"></div><div><label class="label">일사임계</label><input class="input-field" id="solar-' + g.id + '" value="' + g.solar_threshold + '"></div></div><div style="margin-top:10px; display:flex; justify-content:space-between;"><button class="btn btn-detail" onclick="openModal(' + g.id + ')">⚙️ 세부 설정</button><button class="btn btn-primary" style="font-size:11px; padding:4px 10px;" onclick="saveBasic(' + g.id + ')">저장</button></div></div>';
                    });
                    document.getElementById('group-container').innerHTML = html;
                });
            }
            function openModal(id) {
                const g = currentGroups.find(x => x.id === id);
                document.getElementById('modal-group-id').value = id;
                document.getElementById('modal-title').innerText = g.name + ' 세부 설정';
                document.getElementById('m-start').value = g.start_time;
                document.getElementById('m-end').value = g.end_time;
                document.getElementById('m-min-rad').value = g.min_radiation;
                document.getElementById('m-fixed-int').value = g.fixed_interval;
                document.getElementById('m-rinse').value = g.rinse_duration;
                document.getElementById('m-interval').value = g.interval;
                document.getElementById('detailModal').style.display = 'block';
            }
            function closeModal() { document.getElementById('detailModal').style.display = 'none'; }
            function saveBasic(id) {
                const s = { target_ec: parseFloat(document.getElementById('ec-'+id).value), solar_threshold: parseFloat(document.getElementById('solar-'+id).value) };
                fetch('/api/groups/update', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({id, settings: s}) }).then(() => alert('저장됨'));
            }
            function saveModalSettings() {
                const id = parseInt(document.getElementById('modal-group-id').value);
                const s = { start_time: document.getElementById('m-start').value, end_time: document.getElementById('m-end').value, min_radiation: parseFloat(document.getElementById('m-min-rad').value), fixed_interval: parseInt(document.getElementById('m-fixed-int').value), rinse_duration: parseInt(document.getElementById('m-rinse').value), interval: parseInt(document.getElementById('m-interval').value) };
                fetch('/api/groups/update', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({id, settings: s}) }).then(() => { alert('세부 설정 저장됨'); closeModal(); updateUI(); });
            }
            function saveAir() {
                const s = { target_temp: parseFloat(document.getElementById('target_temp').value), temp_deadband: parseFloat(document.getElementById('temp_deadband').value) };
                fetch('/api/air/update', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(s) }).then(() => alert('설정 저장됨'));
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
        "air": {"target_temp": state.control.target_temp, "temp_deadband": state.control.temp_deadband}
    })

@app.route('/api/air/update', methods=['POST'])
def update_air():
    data = request.json
    state.control.target_temp = data['target_temp']
    state.control.temp_deadband = data['temp_deadband']
    state.db.set_config("target_temp", data['target_temp'])
    state.db.set_config("temp_deadband", data['temp_deadband'])
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
