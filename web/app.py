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
        # 환경 변수나 설정에 따라 모드 결정 (기본값: SIM)
        self.mode = os.getenv("CONTROL_MODE", "SIM")
        
        if self.mode == "MODBUS":
            self.collector = ModbusCollector(host="127.0.0.1", port=502)
            # Modbus 클라이언트를 제어부와 공유
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
            print(f"[System] {data['error']}")
            time.sleep(5)
            continue
            
        state.current_data = data
        state.control.process(data, collector=state.collector)
        
        count += 1
        if count >= 5: 
            state.db.save_data(data)
            count = 0
        time.sleep(2)

# ... (기존 API 엔드포인트 및 index() 함수 동일)
@app.route('/')
def index():
    return f"<!-- Mode: {state.mode} -->" + """
    <!DOCTYPE html>
    <html>
    <head>
        <title>스마트 온실 통합 제어 시스템</title>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <style>
            body { font-family: 'Malgun Gothic', 'Apple SD Gothic Neo', sans-serif; margin: 40px; background-color: #f0f4f0; color: #333; }
            .container { max-width: 1000px; margin: auto; }
            .card { background: white; padding: 25px; border-radius: 15px; box-shadow: 0 4px 15px rgba(0,0,0,0.08); margin-bottom: 25px; }
            .grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; }
            .data-box { text-align: center; padding: 15px; background: #f9fdf9; border-radius: 10px; border: 1px solid #e0eee0; }
            .data-point { font-size: 24px; font-weight: bold; color: #2e7d32; margin-top: 5px; }
            .label { color: #777; font-size: 13px; font-weight: bold; }
            h1, h2 { color: #1b5e20; }
            .chart-container { height: 300px; margin-top: 20px; }
            input { padding: 8px; border: 1px solid #ddd; border-radius: 5px; width: 80px; }
            button { padding: 10px 25px; cursor: pointer; background-color: #4caf50; color: white; border: none; border-radius: 5px; font-weight: bold; transition: 0.3s; }
            button:hover { background-color: #388e3c; }
            .control-row { display: flex; align-items: center; gap: 20px; margin-top: 15px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🌿 스마트 온실 통합 모니터링</h1>
            <div style="text-align:right; font-size:12px; color:#666;">작동 모드: """ + state.mode + """</div>
            <div class="card">
                <h2>현재 환경 상태</h2>
                <div class="grid">
                    <div class="data-box">
                        <div class="label">내부 온도</div>
                        <div id="temp" class="data-point">--</div>
                    </div>
                    <div class="data-box">
                        <div class="label">포차 (VPD)</div>
                        <div id="vpd" class="data-point">--</div>
                    </div>
                    <div class="data-box">
                        <div class="label">일사 적산량</div>
                        <div id="solar_acc" class="data-point">--</div>
                        <span style="font-size: 10px; color: #999;">J/cm²</span>
                    </div>
                    <div class="data-box">
                        <div class="label">토양 수분</div>
                        <div id="moisture" class="data-point">--</div>
                    </div>
                </div>
            </div>

            <div class="card">
                <h2>실시간 데이터 추이</h2>
                <div class="chart-container">
                    <canvas id="envChart"></canvas>
                </div>
            </div>

            <div class="card">
                <h2>호겐도른 관수 제어 설정</h2>
                <div class="control-row">
                    <div>
                        <label class="label">일사 적산 임계값 (J/cm²)</label><br>
                        <input type="number" id="solar_threshold" value="150">
                    </div>
                    <div>
                        <label class="label">최저 토양 수분 (%)</label><br>
                        <input type="number" id="moisture_threshold" value="30">
                    </div>
                    <button onclick="updateSettings()">설정 저장 및 적용</button>
                </div>
            </div>
        </div>

        <script>
            let chart;
            function initChart() {
                const ctx = document.getElementById('envChart').getContext('2d');
                chart = new Chart(ctx, {
                    type: 'line',
                    data: {
                        labels: [],
                        datasets: [
                            { label: '온도 (°C)', data: [], borderColor: '#ff7043', tension: 0.3, yAxisID: 'y' },
                            { label: '토양 수분 (%)', data: [], borderColor: '#42a5f5', tension: 0.3, yAxisID: 'y1' }
                        ]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        scales: {
                            y: { type: 'linear', display: true, position: 'left', title: { display: true, text: '온도' } },
                            y1: { type: 'linear', display: true, position: 'right', grid: { drawOnChartArea: false }, title: { display: true, text: '수분' } }
                        }
                    }
                });
            }

            function updateUI() {
                fetch('/api/data')
                    .then(r => r.json())
                    .then(data => {
                        if (data.error) {
                            console.error(data.error);
                            return;
                        }
                        document.getElementById('temp').innerText = (data.temp || 0) + '°C';
                        document.getElementById('vpd').innerText = (data.vpd || 0) + ' kPa';
                        document.getElementById('solar_acc').innerText = data.solar_accumulation || 0;
                        document.getElementById('moisture').innerText = (data.moisture || 0) + '%';
                    });
                
                fetch('/api/history')
                    .then(r => r.json())
                    .then(history => {
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
                    body: JSON.stringify({
                        solar_threshold: parseFloat(solar),
                        moisture_threshold: parseFloat(moisture)
                    })
                }).then(() => alert('제어 설정이 저장되었습니다.'));
            }

            initChart();
            setInterval(updateUI, 2000);
        </script>
    </body>
    </html>
    """

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
