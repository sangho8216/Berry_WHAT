import sys
import os
import time
from web.app import app as flask_app
from core.logic import SystemControl
from interface.collector import SimulatedCollector, ModbusCollector

def run_cli_mode():
    print("Starting Berry_WHAT CLI Mode...")
    # 환경 변수에 따라 적절한 컬렉터 선택
    mode = os.getenv("CONTROL_MODE", "SIM")
    if mode == "MODBUS":
        collector = ModbusCollector(host="127.0.0.1", port=502)
    else:
        collector = SimulatedCollector()
    
    engine = SystemControl()
    
    try:
        while True:
            data = collector.collect_signals()
            if "error" in data:
                print(f"[Error] {data['error']}")
            else:
                engine.process(data, collector=collector)
            time.sleep(2)
    except KeyboardInterrupt:
        print("\nShutting down.")

if __name__ == "__main__":
    # 웹 모드 실행: python3 main.py --web
    if len(sys.argv) > 1 and sys.argv[1] == "--web":
        from web.app import start_backend
        start_backend()
        print("Starting Berry_WHAT Web Dashboard at http://localhost:8080")
        flask_app.run(host='0.0.0.0', port=8080)
    else:
        run_cli_mode()
