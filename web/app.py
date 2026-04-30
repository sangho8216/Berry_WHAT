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
    actuator_status = None
    while state.running:
        data = state.collector.collect_signals(actuator_status=actuator_status)
        if "error" not in data:
            data["status"] = "Connected"
            state.current_data = data
            state.control.process(data, collector=state.collector)
            state.db.save_data(data)
            actuator_status = state.control.get_actuator_status()
        time.sleep(2)


@app.route('/')
def index():
    settings = state.control.get_settings()
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Berry_WHAT Precision Control v3.0</title>
        <style>
            body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; background-color: #1c2833; color: #ecf0f1; font-size: 14px; }
            .header { background: #2c3e50; padding: 15px 25px; display: flex; justify-content: space-between; align-items: center; border-bottom: 3px solid #27ae60; }
            .main-container { display: flex; flex-direction: column; gap: 20px; padding: 20px; }
            
            .system-row { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
            .card { background: #2e4053; border-radius: 10px; padding: 20px; box-shadow: 0 4px 15px rgba(0,0,0,0.5); border: 1px solid #34495e; }
            .card-header { font-size: 18px; font-weight: bold; margin-bottom: 15px; border-bottom: 2px solid #2ecc71; padding-bottom: 10px; display: flex; justify-content: space-between; align-items: center; }
            .card-header .mode-toggle { font-size: 12px; background: #34495e; padding: 4px 8px; border-radius: 4px; cursor: pointer; border: 1px solid #2ecc71; }
            .card-header .mode-toggle.active { background: #2ecc71; color: #145a32; }
            
            .data-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; }
            .data-item { background: #1b2631; padding: 15px; border-radius: 6px; text-align: center; position: relative; }
            .data-label { font-size: 12px; color: #bdc3c7; margin-bottom: 5px; }
            .data-value { font-size: 24px; font-weight: bold; color: #fff; }
            .data-unit { font-size: 14px; color: #2ecc71; margin-left: 4px; }

            .step-indicator { flex: 1; text-align: center; padding: 10px; background: #34495e; border-radius: 4px; font-size: 12px; color: #7f8c8d; border-bottom: 4px solid transparent; transition: 0.3s; }
            .step-indicator.active { background: #2ecc71; color: #145a32; font-weight: bold; border-bottom-color: #27ae60; }
            .convergence-bar { height: 4px; background: #1b2631; border-radius: 2px; margin-top: 5px; overflow: hidden; }
            .convergence-fill { height: 100%; background: #2ecc71; width: 0%; transition: 0.5s; }

            .system-diagram { height: 280px; background: #1b2631; border-radius: 8px; position: relative; border: 1px solid #455a64; margin-top: 15px; display: flex; flex-direction: column; justify-content: center; align-items: center; padding: 10px; gap: 20px; }
            .tank-row { display: flex; gap: 20px; align-items: flex-end; }
            .component { width: 55px; height: 70px; background: #3498db; border-radius: 5px; display: flex; flex-direction: column; align-items: center; justify-content: center; font-size: 10px; text-align: center; color: white; border: 2px solid #2980b9; position: relative; transition: 0.3s; }
            .component.tank-a { background: #e67e22; border-color: #d35400; }
            .component.tank-b { background: #f1c40f; border-color: #f39c12; color: #2c3e50; }
            .component.tank-acid { background: #e74c3c; border-color: #c0392b; }
            .component.active { box-shadow: 0 0 15px #2ecc71; border-color: #2ecc71; transform: scale(1.05); }
            
            .valve { width: 12px; height: 12px; background: #95a5a6; border-radius: 2px; position: absolute; bottom: -15px; border: 1px solid #fff; }
            .valve.active { background: #2ecc71; }

            .mixing-unit { display: flex; align-items: center; gap: 15px; padding: 10px; background: #2c3e50; border-radius: 8px; border: 1px dashed #7f8c8d; }
            .pump { width: 35px; height: 35px; border-radius: 50%; background: #9b59b6; border: 2px solid #8e44ad; display: flex; align-items: center; justify-content: center; font-size: 8px; transition: 0.3s; }
            .pump.active { background: #2ecc71; border-color: #27ae60; box-shadow: 0 0 10px #2ecc71; animation: spin 2s linear infinite; }
            @keyframes spin { from {transform: rotate(0deg);} to {transform: rotate(360deg);} }

            .manual-controls { margin-top: 15px; display: grid; grid-template-columns: repeat(3, 1fr); gap: 5px; }
            .ctrl-btn { font-size: 10px; padding: 6px; background: #34495e; border: 1px solid #5d6d7e; color: #fff; cursor: pointer; border-radius: 4px; text-align: center; }
            .ctrl-btn.active { background: #2ecc71; color: #145a32; border-color: #27ae60; }

            .settings-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; margin-top: 15px; }
            .input-group label { display: block; font-size: 11px; margin-bottom: 4px; color: #bdc3c7; }
            input { width: 100%; padding: 8px; background: #1c2833; border: 1px solid #5d6d7e; color: #fff; border-radius: 4px; box-sizing: border-box; }
            button { width: 100%; padding: 12px; background: #27ae60; color: white; border: none; border-radius: 6px; font-weight: bold; cursor: pointer; transition: 0.3s; margin-top: 15px; }
            button:hover { background: #2ecc71; transform: translateY(-2px); }
        </style>
    </head>
    <body>
        <div class="header">
            <div style="display:flex; align-items:center; gap:15px;">
                <span style="font-size: 24px;">🍓</span>
                <div>
                    <div style="font-size: 20px; font-weight: bold;">Berry_WHAT 스마트 온실</div>
                    <div style="font-size: 12px; color: #bdc3c7;">통합 환경 및 양액 제어 시스템 v3.0 (Industrial Std.)</div>
                </div>
            </div>
            <div style="text-align: right;">
                <div id="current-time" style="font-weight: bold; color: #f1c40f;">----.--.-- --:--:--</div>
                <div style="font-size: 12px; color: #bdc3c7;">일출 <span id="sunrise">--:--</span> | 일몰 <span id="sunset">--:--</span></div>
            </div>
        </div>

        <div class="main-container">
            <!-- 0. 공정 플로우 (Process Flow) -->
            <div class="card" style="margin-bottom: 0;">
                <div class="card-header">🔄 공정 상태 (Process Flow) <span id="current-state-text" style="color: #f1c40f;">STANDBY</span></div>
                <div style="display: flex; justify-content: space-between; padding: 10px 0; overflow-x: auto; gap: 10px;">
                    <div class="step-indicator" id="step-STANDBY">대기</div>
                    <div class="step-indicator" id="step-PRE_RINSE">전세척</div>
                    <div class="step-indicator" id="step-MIXING">배합</div>
                    <div class="step-indicator" id="step-STABILIZATION">안정화</div>
                    <div class="step-indicator" id="step-IRRIGATION">관수</div>
                    <div class="step-indicator" id="step-POST_RINSE">후세척</div>
                    <div class="step-indicator" id="step-ALARM" style="background: #c0392b; display:none;">경보</div>
                </div>
            </div>

            <!-- 1. 기후 제어 시스템 -->
            <div class="system-row">
                <div class="card">
                    <div class="card-header">🌡️ 기후 모니터링 <span>Climate</span></div>
                    <div class="data-grid">
                        <div class="data-item"><div class="data-label">내부 온도</div><div class="data-value"><span id="temp">--.-</span><span class="data-unit">°C</span></div></div>
                        <div class="data-item"><div class="data-label">상대 습도</div><div class="data-value"><span id="humidity">--.-</span><span class="data-unit">%</span></div></div>
                        <div class="data-item"><div class="data-label">포차 (VPD)</div><div class="data-value"><span id="vpd">-.--</span><span class="data-unit">kPa</span></div></div>
                        <div class="data-item"><div class="data-label">일사량</div><div class="data-value"><span id="solar_rad">---</span><span class="data-unit">W/m²</span></div></div>
                    </div>
                </div>
                <div class="card">
                    <div class="card-header">⚙️ 기후 설정</div>
                    <div class="settings-grid">
                        <div class="input-group"><label>목표 온도 (°C)</label><input type="number" id="target_temp" step="0.5"></div>
                        <div class="input-group"><label>온도 데드밴드</label><input type="number" id="temp_deadband" step="0.1"></div>
                        <div class="input-group"><label>최저 VPD (kPa)</label><input type="number" id="target_vpd_min" step="0.1"></div>
                        <div class="input-group"><label>최고 VPD (kPa)</label><input type="number" id="target_vpd_max" step="0.1"></div>
                    </div>
                    <button onclick="saveSettings()">기후 설정 저장</button>
                </div>
            </div>

            <!-- 2. 양액 제어 시스템 -->
            <div class="system-row">
                <div class="card">
                    <div class="card-header">
                        💧 양액 및 관수 <span>Nutrient</span>
                        <div class="mode-toggle" id="nutrient-mode" onclick="toggleNutrientMode()">AUTO</div>
                    </div>
                    <div class="data-grid">
                        <div class="data-item">
                            <div class="data-label">현재 EC</div>
                            <div class="data-value" id="ec-val">-.--</div>
                            <div class="convergence-bar"><div class="convergence-fill" id="ec-conv"></div></div>
                        </div>
                        <div class="data-item">
                            <div class="data-label">현재 pH</div>
                            <div class="data-value" id="ph-val">-.--</div>
                            <div class="convergence-bar"><div class="convergence-fill" id="ph-conv"></div></div>
                        </div>
                        <div class="data-item"><div class="data-label">토양 수분</div><div class="data-value"><span id="moisture">--.-</span><span class="data-unit">%</span></div></div>
                        <div class="data-item"><div class="data-label">일사 적산</div><div class="data-value"><span id="solar_acc">---</span><span class="data-unit">J/cm²</span></div></div>
                    </div>
                    
                    <div class="system-diagram">
                        <div class="tank-row">
                            <div class="component tank-a" id="viz-valve-A">A탱크<div class="valve" id="viz-v-A"></div></div>
                            <div class="component tank-b" id="viz-valve-B">B탱크<div class="valve" id="viz-v-B"></div></div>
                            <div class="component tank-acid" id="viz-valve-ACID">산탱크<div class="valve" id="viz-v-ACID"></div></div>
                            <div class="component">원수<div class="valve active"></div></div>
                        </div>
                        <div class="mixing-unit">
                            <div class="pump" id="viz-mixing-pump">MIX</div>
                            <div class="component" style="height:40px; width:80px;">혼합탱크</div>
                            <div class="pump" id="viz-supply-pump">SUP</div>
                        </div>
                    </div>

                    <div class="manual-controls" id="manual-buttons" style="display:none;">
                        <div class="ctrl-btn" onclick="toggleActuator('valves', 'A')">A 밸브</div>
                        <div class="ctrl-btn" onclick="toggleActuator('valves', 'B')">B 밸브</div>
                        <div class="ctrl-btn" onclick="toggleActuator('valves', 'ACID')">산 밸브</div>
                        <div class="ctrl-btn" onclick="toggleActuator('pumps', 'MIXING')">혼합 펌프</div>
                        <div class="ctrl-btn" onclick="toggleActuator('pumps', 'SUPPLY')">공급 펌프</div>
                        <div class="ctrl-btn" onclick="toggleActuator('valves', 'MAIN')">메인 밸브</div>
                    </div>
                </div>
                <div class="card">
                    <div class="card-header">⚙️ 양액 설정</div>
                    <div class="settings-grid">
                        <div class="input-group"><label>목표 EC</label><input type="number" id="target_ec" step="0.1"></div>
                        <div class="input-group"><label>목표 pH</label><input type="number" id="target_ph" step="0.1"></div>
                        <div class="input-group"><label>일사 임계치</label><input type="number" id="solar_threshold"></div>
                        <div class="input-group"><label>최저 수분 (%)</label><input type="number" id="min_moisture"></div>
                    </div>
                    <button onclick="saveSettings()" style="background:#2980b9;">양액 설정 저장</button>
                    <div style="margin-top: 15px; font-size: 12px; color: #bdc3c7; text-align: center;">오늘 공급 횟수: <b id="today_supply" style="color:#f1c40f;">--</b></div>
                </div>
            </div>
        </div>

        <script>
            let currentSettings = {};

            function toggleNutrientMode() {
                const isManual = currentSettings.manual_mode;
                saveSettings({ manual_mode: !isManual });
            }

            function toggleActuator(type, key) {
                if (!currentSettings.manual_mode) return;
                const path = type === 'valves' ? 'manual_valves' : 'manual_pumps';
                const newState = !currentSettings[path][key];
                const update = {};
                update[path] = { ...currentSettings[path] };
                update[path][key] = newState;
                saveSettings(update);
            }

            function updateUI() {
                const now = new Date();
                document.getElementById('current-time').innerText = now.toLocaleString();

                fetch('/api/data').then(r => r.json()).then(data => {
                    if(data.temp) {
                        document.getElementById('temp').innerText = data.temp;
                        document.getElementById('humidity').innerText = data.humidity;
                        document.getElementById('vpd').innerText = data.vpd;
                        document.getElementById('solar_rad').innerText = data.solar_radiation;
                        document.getElementById('ec-val').innerText = data.ec;
                        document.getElementById('ph-val').innerText = data.ph;
                        document.getElementById('moisture').innerText = data.moisture;
                        document.getElementById('solar_acc').innerText = data.solar_accumulation;
                    }
                });

                fetch('/api/status').then(r => r.json()).then(status => {
                    const acts = status.actuators;
                    document.getElementById('sunrise').innerText = acts.sunrise;
                    document.getElementById('sunset').innerText = acts.sunset;
                    document.getElementById('today_supply').innerText = acts.today_supply;
                    
                    const updateState = (id, isActive) => {
                        const el = document.getElementById(id);
                        if(el) isActive ? el.classList.add('active') : el.classList.remove('active');
                    };

                    updateState('viz-valve-A', acts.valves.A); updateState('viz-v-A', acts.valves.A);
                    updateState('viz-valve-B', acts.valves.B); updateState('viz-v-B', acts.valves.B);
                    updateState('viz-valve-ACID', acts.valves.ACID); updateState('viz-v-ACID', acts.valves.ACID);
                    updateState('viz-mixing-pump', acts.mixing_pump === 'On');
                    updateState('viz-supply-pump', acts.supply_pump === 'On');
                    
                    // 공정 상태 업데이트
                    document.getElementById('current-state-text').innerText = acts.nutrient_state;
                    const steps = ['STANDBY', 'PRE_RINSE', 'MIXING', 'STABILIZATION', 'IRRIGATION', 'POST_RINSE', 'ALARM'];
                    steps.forEach(s => {
                        const el = document.getElementById('step-' + s);
                        if(el) {
                            if(s === acts.nutrient_state) {
                                el.classList.add('active');
                                if(s === 'ALARM') el.style.display = 'block';
                            } else {
                                el.classList.remove('active');
                                if(s === 'ALARM') el.style.display = 'none';
                            }
                        }
                    });

                    // 수렴도 계산 (EC/pH)
                    if (currentSettings.target_ec > 0) {
                        const ecVal = parseFloat(document.getElementById('ec-val').innerText);
                        const ecDiff = Math.abs(ecVal - currentSettings.target_ec);
                        const ecConv = Math.max(0, 100 - (ecDiff / 0.5) * 100);
                        document.getElementById('ec-conv').style.width = ecConv + '%';
                    }
                    if (currentSettings.target_ph > 0) {
                        const phVal = parseFloat(document.getElementById('ph-val').innerText);
                        const phDiff = Math.abs(phVal - currentSettings.target_ph);
                        const phConv = Math.max(0, 100 - (phDiff / 1.0) * 100);
                        document.getElementById('ph-conv').style.width = phConv + '%';
                    }
                    
                    if (currentSettings.manual_mode) {
                        const btns = document.querySelectorAll('.ctrl-btn');
                        btns.forEach(b => {
                            if(b.innerText.includes('A 밸브')) acts.valves.A ? b.classList.add('active') : b.classList.remove('active');
                            if(b.innerText.includes('B 밸브')) acts.valves.B ? b.classList.add('active') : b.classList.remove('active');
                            if(b.innerText.includes('산 밸브')) acts.valves.ACID ? b.classList.add('active') : b.classList.remove('active');
                            if(b.innerText.includes('혼합 펌프')) acts.mixing_pump === 'On' ? b.classList.add('active') : b.classList.remove('active');
                            if(b.innerText.includes('공급 펌프')) acts.supply_pump === 'On' ? b.classList.add('active') : b.classList.remove('active');
                            if(b.innerText.includes('메인 밸브')) acts.valves.MAIN ? b.classList.add('active') : b.classList.remove('active');
                        });
                    }
                });

                fetch('/api/settings').then(r => r.json()).then(s => {
                    currentSettings = s;
                    const modeEl = document.getElementById('nutrient-mode');
                    modeEl.innerText = s.manual_mode ? 'MANUAL' : 'AUTO';
                    s.manual_mode ? modeEl.classList.add('active') : modeEl.classList.remove('active');
                    document.getElementById('manual-buttons').style.display = s.manual_mode ? 'grid' : 'none';

                    if (document.activeElement.tagName !== 'INPUT') {
                        ['target_temp', 'temp_deadband', 'target_vpd_min', 'target_vpd_max',
                         'target_ec', 'target_ph', 'solar_threshold', 'min_moisture'].forEach(id => {
                             const el = document.getElementById(id);
                             if(el) el.value = s[id];
                         });
                    }
                });
            }

            function saveSettings(customUpdate = null) {
                let settings = customUpdate;
                if (!settings) {
                    settings = {};
                    document.querySelectorAll('.settings-grid input').forEach(input => {
                        settings[input.id] = parseFloat(input.value);
                    });
                }
                fetch('/api/settings', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(settings)
                }).then(() => updateUI());
            }

            setInterval(updateUI, 2000);
            updateUI();
        </script>
    </body>
    </html>
    """

@app.route('/api/status')
def get_status():
    return jsonify({"actuators": state.control.get_actuator_status()})

@app.route('/api/data')
def get_data():
    return jsonify(state.current_data)

@app.route('/api/settings', methods=['GET', 'POST'])
def handle_settings():
    if request.method == 'POST':
        state.control.update_settings(request.json)
        return jsonify({"status": "success"})
    return jsonify(state.control.get_settings())


# 백엔드 제어 루프 스레드 시작 (메인 실행 시에만)
def start_backend():
    print("[Web] 제어 루프 스레드 시작 중...")
    t = threading.Thread(target=control_loop)
    t.daemon = True
    t.start()
    print("[Web] 제어 루프 스레드 시작 완료.")

if __name__ == '__main__':
    start_backend()
    print("[Web] Flask 서버 시작 중 (Port 8080)...")
    app.run(host='0.0.0.0', port=8080)
