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
            state.db.save_data(data)
        time.sleep(2)

@app.route('/')
def index():
    settings = state.control.get_settings()
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Berry_WHAT Precision Control</title>
        <style>
            body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; background-color: #2c3e50; color: #ecf0f1; }
            .header { background: #34495e; padding: 10px 20px; display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #2ecc71; }
            .time-info { display: flex; gap: 20px; font-size: 14px; }
            .time-info span b { color: #f1c40f; }
            
            .main-grid { display: grid; grid-template-columns: 2fr 1fr; gap: 10px; padding: 10px; }
            .card { background: #3e4f5f; border-radius: 8px; padding: 15px; box-shadow: 0 2px 10px rgba(0,0,0,0.3); }
            
            .gauge-container { display: flex; gap: 10px; margin-bottom: 10px; }
            .gauge { flex: 1; background: #2c3e50; border-radius: 8px; padding: 15px; border: 1px solid #455a64; text-align: center; }
            .gauge-title { font-size: 18px; font-weight: bold; color: #2ecc71; text-align: left; }
            .gauge-value { font-size: 32px; font-weight: bold; margin: 10px 0; color: #fff; }
            .gauge-targets { font-size: 14px; color: #bdc3c7; display: flex; justify-content: space-around; }
            .gauge-targets b { color: #e74c3c; }

            .system-diagram { height: 250px; background: #2c3e50; border-radius: 8px; position: relative; border: 1px solid #455a64; margin-top: 10px; display: flex; justify-content: space-around; align-items: center; padding: 20px; }
            .component { width: 60px; height: 80px; background: #3498db; border-radius: 5px; display: flex; flex-direction: column; align-items: center; justify-content: center; font-size: 10px; text-align: center; color: white; border: 2px solid #2980b9; }
            .component.pump { width: 40px; height: 40px; border-radius: 50%; background: #9b59b6; border: 2px solid #8e44ad; }
            .component.active { background: #2ecc71; border-color: #27ae60; box-shadow: 0 0 10px #2ecc71; }

            .info-table { width: 100%; border-collapse: collapse; font-size: 13px; }
            .info-table td { padding: 8px; border-bottom: 1px solid #455a64; }
            .info-table td:last-child { text-align: right; font-weight: bold; color: #f1c40f; }

            .settings-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
            .input-group { margin-bottom: 10px; }
            label { display: block; font-size: 11px; color: #bdc3c7; margin-bottom: 2px; }
            input { width: 100%; padding: 6px; background: #2c3e50; border: 1px solid #455a64; color: white; border-radius: 4px; }
            button { width: 100%; padding: 10px; background: #2ecc71; color: white; border: none; border-radius: 4px; font-weight: bold; cursor: pointer; margin-top: 10px; }
            button:hover { background: #27ae60; }

            .status-bar { height: 30px; background: #1a252f; border-radius: 4px; margin-top: 10px; display: flex; align-items: center; justify-content: center; font-size: 12px; position: relative; overflow: hidden; }
            .progress { position: absolute; left: 0; top: 0; bottom: 0; background: #2ecc71; opacity: 0.3; }
        </style>
    </head>
    <body>
        <div class="header">
            <div style="font-size: 20px; font-weight: bold;">Berry_WHAT 양액 제어 시스템 <span style="font-size: 12px; font-weight: normal; color: #bdc3c7;">v1.46</span></div>
            <div class="time-info">
                <span>일출 <b><span id="sunrise">--:--</span></b></span>
                <span>일몰 <b><span id="sunset">--:--</span></b></span>
                <span id="current-time">---- -- -- --:--:--</span>
            </div>
        </div>

        <div class="main-grid">
            <div>
                <div class="gauge-container">
                    <div class="gauge">
                        <div class="gauge-title">EC</div>
                        <div class="gauge-value" id="ec-val">--.--</div>
                        <div class="gauge-targets">
                            <span>목표값: <b id="target_ec_display">--</b></span>
                            <span>제어값: <b id="control_ec_display">--</b></span>
                        </div>
                    </div>
                    <div class="gauge">
                        <div class="gauge-title">pH</div>
                        <div class="gauge-value" id="ph-val">--.--</div>
                        <div class="gauge-targets">
                            <span>목표값: <b id="target_ph_display">--</b></span>
                            <span>제어값: <b id="control_ph_display">--</b></span>
                        </div>
                    </div>
                </div>

                <div class="status-bar">
                    <div class="progress" style="width: 0%;"></div>
                    <span id="supply-status">대기 중</span>
                </div>

                <div class="system-diagram">
                    <div class="component">원수탱크</div>
                    <div class="component pump" id="mixing-pump-viz">혼합<br>펌프</div>
                    <div class="component">혼합탱크</div>
                    <div class="component pump" id="supply-pump-viz">공급<br>펌프</div>
                    <div class="component">교반기</div>
                    <div style="display:grid; grid-template-columns: repeat(3, 1fr); gap: 5px;">
                        <div style="width:10px; height:10px; background:#455a64; border-radius:2px;"></div>
                        <div style="width:10px; height:10px; background:#455a64; border-radius:2px;"></div>
                        <div style="width:10px; height:10px; background:#455a64; border-radius:2px;"></div>
                        <div style="width:10px; height:10px; background:#2ecc71; border-radius:2px;"></div>
                        <div style="width:10px; height:10px; background:#455a64; border-radius:2px;"></div>
                    </div>
                </div>
            </div>

            <div>
                <div class="card" style="margin-bottom: 10px;">
                    <table class="info-table">
                        <tr><td>제어방식</td><td id="control_mode">--</td></tr>
                        <tr><td>제어코드</td><td id="control_code">--</td></tr>
                        <tr><td>공급단위</td><td>리터</td></tr>
                        <tr><td>현재 일사광</td><td id="solar_rad">-- W/m²</td></tr>
                        <tr><td>현재 함수율</td><td id="water_content">-- %</td></tr>
                        <tr><td>현재 유량</td><td id="flow_rate">-- L/min</td></tr>
                        <tr><td>오늘 공급</td><td id="today_supply">--</td></tr>
                    </table>
                </div>

                <div class="card">
                    <div style="font-weight: bold; margin-bottom: 10px; border-bottom: 1px solid #455a64; padding-bottom: 5px;">시스템 설정</div>
                    <div class="settings-grid">
                        <div class="input-group"><label>목표 EC</label><input type="number" id="target_ec" step="0.1"></div>
                        <div class="input-group"><label>목표 pH</label><input type="number" id="target_ph" step="0.1"></div>
                        <div class="input-group"><label>일사 임계치</label><input type="number" id="solar_threshold"></div>
                        <div class="input-group"><label>최저 수분</label><input type="number" id="min_moisture"></div>
                        <div class="input-group"><label>관수 시간(초)</label><input type="number" id="duration"></div>
                        <div class="input-group"><label>관수 간격(분)</label><input type="number" id="interval"></div>
                    </div>
                    <button onclick="saveSettings()">설정 적용</button>
                </div>
            </div>
        </div>

        <script>
            function updateUI() {
                const now = new Date();
                document.getElementById('current-time').innerText = now.toLocaleString();

                fetch('/api/data').then(r => r.json()).then(data => {
                    if(data.ec) {
                        document.getElementById('ec-val').innerText = data.ec;
                        document.getElementById('control_ec_display').innerText = data.ec;
                        document.getElementById('ph-val').innerText = data.ph;
                        document.getElementById('control_ph_display').innerText = data.ph;
                        document.getElementById('solar_rad').innerText = data.solar_radiation + ' W/m²';
                        document.getElementById('water_content').innerText = data.water_content + ' %';
                        document.getElementById('flow_rate').innerText = data.flow_rate + ' L/min';
                    }
                });

                fetch('/api/status').then(r => r.json()).then(status => {
                    document.getElementById('sunrise').innerText = status.actuators.sunrise;
                    document.getElementById('sunset').innerText = status.actuators.sunset;
                    document.getElementById('today_supply').innerText = status.actuators.today_supply;
                    
                    const isIrrigating = status.actuators.irrigation.includes('On');
                    document.getElementById('supply-status').innerText = isIrrigating ? '공급 중...' : '대기 중';
                    document.querySelector('.progress').style.width = isIrrigating ? '100%' : '0%';
                    
                    document.getElementById('mixing-pump-viz').className = 'component pump' + (status.actuators.mixing_pump === 'On' ? ' active' : '');
                    document.getElementById('supply-pump-viz').className = 'component pump' + (status.actuators.supply_pump === 'On' ? ' active' : '');
                });

                fetch('/api/settings').then(r => r.json()).then(settings => {
                    document.getElementById('target_ec_display').innerText = settings.target_ec;
                    document.getElementById('target_ph_display').innerText = settings.target_ph;
                    document.getElementById('control_mode').innerText = settings.control_mode;
                    document.getElementById('control_code').innerText = settings.control_code;
                    
                    // Only update inputs if they are not being edited (simple check)
                    if (document.activeElement.tagName !== 'INPUT') {
                        document.getElementById('target_ec').value = settings.target_ec;
                        document.getElementById('target_ph').value = settings.target_ph;
                        document.getElementById('solar_threshold').value = settings.solar_threshold;
                        document.getElementById('min_moisture').value = settings.min_moisture;
                        document.getElementById('duration').value = settings.duration;
                        document.getElementById('interval').value = settings.interval;
                    }
                });
            }

            function saveSettings() {
                const settings = {
                    target_ec: parseFloat(document.getElementById('target_ec').value),
                    target_ph: parseFloat(document.getElementById('target_ph').value),
                    solar_threshold: parseFloat(document.getElementById('solar_threshold').value),
                    min_moisture: parseFloat(document.getElementById('min_moisture').value),
                    duration: parseInt(document.getElementById('duration').value),
                    interval: parseInt(document.getElementById('interval').value)
                };
                fetch('/api/settings', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(settings)
                }).then(() => alert('설정이 시스템에 반영되었습니다.'));
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
