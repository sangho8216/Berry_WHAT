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
    settings = state.control.get_settings()
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>스마트 온실 통합 제어 시스템</title>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <style>
            body { font-family: 'Malgun Gothic', sans-serif; margin: 40px; background-color: #f4f7f4; color: #333; }
            .container { max-width: 1200px; margin: auto; }
            .card { background: white; padding: 25px; border-radius: 15px; box-shadow: 0 4px 15px rgba(0,0,0,0.08); margin-bottom: 25px; }
            .grid-4 { display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; }
            .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 25px; }
            .data-box { text-align: center; padding: 15px; background: #f9fdf9; border-radius: 10px; border: 1px solid #e0eee0; }
            .data-point { font-size: 24px; font-weight: bold; color: #2e7d32; }
            .label { color: #777; font-size: 13px; font-weight: bold; margin-bottom: 5px; }
            h1, h2 { color: #1b5e20; border-left: 5px solid #4caf50; padding-left: 10px; }
            .input-group { margin-bottom: 15px; }
            label { display: block; font-size: 12px; color: #666; margin-bottom: 3px; }
            input { width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 5px; box-sizing: border-box; }
            button { width: 100%; padding: 12px; background: #2e7d32; color: white; border: none; border-radius: 5px; font-weight: bold; cursor: pointer; }
            .status-item { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #eee; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🌿 Berry_WHAT 정밀 환경제어</h1>
            
            <div class="grid-2">
                <!-- 실시간 상태 섹션 -->
                <div>
                    <div class="card">
                        <h2>환경 모니터링</h2>
                        <div class="grid-4">
                            <div class="data-box"><div class="label">온도</div><div id="temp" class="data-point">--</div></div>
                            <div class="data-box"><div class="label">포차(VPD)</div><div id="vpd" class="data-point">--</div></div>
                            <div class="data-box"><div class="label">일사적산</div><div id="solar_acc" class="data-point">--</div></div>
                            <div class="data-box"><div class="label">토양수분</div><div id="moisture" class="data-point">--</div></div>
                        </div>
                    </div>
                    <div class="card">
                        <h2>구동기 작동 상태</h2>
                        <div id="actuators"></div>
                    </div>
                </div>

                <!-- 설정 섹션 -->
                <div class="card">
                    <h2>양액기 및 관수 세부 설정</h2>
                    <div class="grid-2">
                        <div class="input-group"><label>관수 시작 시간</label><input type="time" id="start_time" value="08:00"></div>
                        <div class="input-group"><label>관수 종료 시간</label><input type="time" id="end_time" value="18:00"></div>
                        <div class="input-group"><label>목표 EC (dS/m)</label><input type="number" id="target_ec" value="2.5" step="0.1"></div>
                        <div class="input-group"><label>목표 pH</label><input type="number" id="target_ph" value="5.8" step="0.1"></div>
                        <div class="input-group"><label>일사 임계치 (J/cm²)</label><input type="number" id="solar_threshold" value="150"></div>
                        <div class="input-group"><label>최저 수분 (%)</label><input type="number" id="min_moisture" value="30"></div>
                        <div class="input-group"><label>1회 관수 시간 (초)</label><input type="number" id="duration" value="60"></div>
                        <div class="input-group"><label>관수 간격 (분)</label><input type="number" id="interval" value="15"></div>
                    </div>
                    <button onclick="saveSettings()">설정 저장 및 시스템 적용</button>
                </div>
            </div>
        </div>

        <script>
            function updateUI() {
                fetch('/api/data').then(r => r.json()).then(data => {
                    if(data.temp) {
                        document.getElementById('temp').innerText = data.temp + '°C';
                        document.getElementById('vpd').innerText = data.vpd + ' kPa';
                        document.getElementById('solar_acc').innerText = data.solar_accumulation;
                        document.getElementById('moisture').innerText = data.moisture + '%';
                    }
                });

                fetch('/api/status').then(r => r.json()).then(status => {
                    let html = '';
                    for (const [key, val] of Object.entries(status.actuators)) {
                        html += `<div class="status-item"><span>${key}</span><b>${val}</b></div>`;
                    }
                    document.getElementById('actuators').innerHTML = html;
                });
            }

            function saveSettings() {
                const settings = {
                    start_time: document.getElementById('start_time').value,
                    end_time: document.getElementById('end_time').value,
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
                }).then(() => alert('양액기 설정이 적용되었습니다.'));
            }

            setInterval(updateUI, 2000);
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

@app.route('/api/settings', methods=['POST'])
def set_settings():
    state.control.update_settings(request.json)
    return jsonify({"status": "success"})

if __name__ == '__main__':
    t = threading.Thread(target=control_loop)
    t.daemon = True
    t.start()
    app.run(host='0.0.0.0', port=5000)
