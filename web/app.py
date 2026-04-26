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
        if self.mode == "MODBUS":
            self.collector = ModbusCollector(host="127.0.0.1", port=502)
            from control.air import AirController
            from control.soil import SoilController
            self.control = SystemControl()
            self.control.air = AirController(mode="MODBUS", client=self.collector.client)
            self.control.soil = SoilController(mode="MODBUS", client=self.collector.client)
        else:
            self.collector = SimulatedCollector()
            self.control = SystemControl()
        
        self.current_data = {}
        self.db = DatabaseManager()
        self.running = True

state = SystemState()

def control_loop():
    count = 0
    while state.running:
        data = state.collector.collect_signals()
        if "error" in data:
            state.current_data = {"error": data["error"], "status": "Disconnected"}
            time.sleep(5)
            continue
            
        data["status"] = "Connected"
        state.current_data = data
        state.control.process(data, collector=state.collector)
        
        count += 1
        if count >= 5: 
            state.db.save_data(data)
            count = 0
        time.sleep(2)

@app.route('/')
def index():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>스마트 온실 통합 제어 시스템</title>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <style>
            body { font-family: 'Malgun Gothic', sans-serif; margin: 40px; background-color: #f0f4f0; color: #333; }
            .container { max-width: 1000px; margin: auto; }
            .card { background: white; padding: 25px; border-radius: 15px; box-shadow: 0 4px 15px rgba(0,0,0,0.08); margin-bottom: 25px; }
            .grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; }
            .data-box { text-align: center; padding: 15px; background: #f9fdf9; border-radius: 10px; border: 1px solid #e0eee0; }
            .data-point { font-size: 24px; font-weight: bold; color: #2e7d32; margin-top: 5px; }
            .label { color: #777; font-size: 13px; font-weight: bold; }
            .status-badge { padding: 4px 10px; border-radius: 20px; font-size: 12px; font-weight: bold; }
            .status-ok { background: #e8f5e9; color: #2e7d32; }
            .status-err { background: #ffebee; color: #c62828; }
            .actuator-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
            .actuator-item { display: flex; justify-content: space-between; padding: 10px; background: #fff; border-bottom: 1px solid #eee; }
            .act-on { color: #2196f3; font-weight: bold; }
            h1, h2 { color: #1b5e20; }
            button { padding: 10px 25px; cursor: pointer; background-color: #4caf50; color: white; border: none; border-radius: 5px; font-weight: bold; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🌿 스마트 온실 통합 모니터링</h1>
            
            <div class="card">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <h2>장치 연결 및 구동 상태</h2>
                    <div>
                        작동 모드: <b id="mode-text">SIM</b>
                        <span id="conn-status" class="status-badge status-ok">연결됨</span>
                    </div>
                </div>
                <div class="actuator-grid">
                    <div class="actuator-item"><span>천창/측창</span> <span id="act-vents">--</span></div>
                    <div class="actuator-item"><span>환풍팬</span> <span id="act-fans">--</span></div>
                    <div class="actuator-item"><span>히터</span> <span id="act-heater">--</span></div>
                    <div class="actuator-item"><span>관수 펌프</span> <span id="act-irrigation">--</span></div>
                </div>
            </div>

            <div class="card">
                <h2>실시간 환경 데이터</h2>
                <div class="grid">
                    <div class="data-box"><div class="label">온도</div><div id="temp" class="data-point">--</div></div>
                    <div class="data-box"><div class="label">VPD</div><div id="vpd" class="data-point">--</div></div>
                    <div class="data-box"><div class="label">일사 적산</div><div id="solar_acc" class="data-point">--</div></div>
                    <div class="data-box"><div class="label">토양 수분</div><div id="moisture" class="data-point">--</div></div>
                </div>
            </div>

            <div class="card">
                <h2>환경 데이터 추이</h2>
                <div style="height:250px;"><canvas id="envChart"></canvas></div>
            </div>

            <div class="card">
                <h2>제어 설정</h2>
                <div style="display:flex; gap:20px;">
                    <div><label class="label">일사 적산 (J/cm²)</label><br><input type="number" id="solar_threshold" value="150" style="padding:8px; width:80px;"></div>
                    <div><label class="label">최저 수분 (%)</label><br><input type="number" id="moisture_threshold" value="30" style="padding:8px; width:80px;"></div>
                    <button onclick="updateSettings()" style="margin-top:20px;">저장</button>
                </div>
            </div>
        </div>

        <script>
            let chart;
            function initChart() {
                const ctx = document.getElementById('envChart').getContext('2d');
                chart = new Chart(ctx, {
                    type: 'line',
                    data: { labels: [], datasets: [
                        { label: '온도 (°C)', data: [], borderColor: '#ff7043', tension: 0.3, yAxisID: 'y' },
                        { label: '수분 (%)', data: [], borderColor: '#42a5f5', tension: 0.3, yAxisID: 'y1' }
                    ]},
                    options: { responsive: true, maintainAspectRatio: false, scales: {
                        y: { type: 'linear', position: 'left' },
                        y1: { type: 'linear', position: 'right', grid: { drawOnChartArea: false } }
                    }}
                });
            }

            function updateUI() {
                fetch('/api/status').then(r => r.json()).then(status => {
                    document.getElementById('mode-text').innerText = status.mode;
                    const conn = document.getElementById('conn-status');
                    conn.innerText = status.connection;
                    conn.className = 'status-badge ' + (status.connection === 'Connected' ? 'status-ok' : 'status-err');
                    
                    for (const [key, val] of Object.entries(status.actuators)) {
                        const el = document.getElementById('act-' + key);
                        if (el) {
                            el.innerText = val;
                            el.className = (val !== 'Off' && val !== 'Closed') ? 'act-on' : '';
                        }
                    }
                });

                fetch('/api/data').then(r => r.json()).then(data => {
                    if(data.temp) {
                        document.getElementById('temp').innerText = data.temp + '°C';
                        document.getElementById('vpd').innerText = data.vpd + ' kPa';
                        document.getElementById('solar_acc').innerText = data.solar_accumulation;
                        document.getElementById('moisture').innerText = data.moisture + '%';
                    }
                });

                fetch('/api/history').then(r => r.json()).then(history => {
                    chart.data.labels = history.map(h => h.timestamp.split(' ')[1]);
                    chart.data.datasets[0].data = history.map(h => h.temp);
                    chart.data.datasets[1].data = history.map(h => h.moisture);
                    chart.update('none');
                });
            }

            function updateSettings() {
                const solar = document.getElementById('solar_threshold').value;
                const moisture = document.getElementById('moisture_threshold').value;
                fetch('/api/settings', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ solar_threshold: parseFloat(solar), moisture_threshold: parseFloat(moisture) })
                }).then(() => alert('저장됨'));
            }

            initChart();
            setInterval(updateUI, 2000);
        </script>
    </body>
    </html>
    """

@app.route('/api/status')
def get_status():
    return jsonify({
        "mode": state.mode,
        "connection": state.current_data.get("status", "Unknown"),
        "actuators": state.control.get_actuator_status()
    })

@app.route('/api/data')
def get_data():
    return jsonify(state.current_data)

@app.route('/api/history')
def get_history():
    return jsonify(state.db.get_history(20))

@app.route('/api/settings', methods=['POST'])
def set_settings():
    state.control.update_setpoints(request.json)
    return jsonify({"status": "success"})

if __name__ == '__main__':
    t = threading.Thread(target=control_loop)
    t.daemon = True
    t.start()
    app.run(host='0.0.0.0', port=5000)
