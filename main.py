import sys
import threading
import time
from core.logic import SystemControl
from interface.collector import DataCollector

def run_cli_mode():
    print("Starting Berry_WHAT CLI Mode...")
    collector = DataCollector()
    engine = SystemControl()
    try:
        # Run 3 iterations for testing and then exit
        for _ in range(3):
            data = collector.collect_signals()
            engine.process(data)
            time.sleep(2)
    except KeyboardInterrupt:
        print("\nShutting down.")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--web":
        try:
            from web.app import app as flask_app
            print("Starting Berry_WHAT Web Dashboard at http://localhost:5000")
            flask_app.run(host='0.0.0.0', port=5000)
        except ImportError:
            print("Error: Flask is not installed. Web mode unavailable.")
            sys.exit(1)
    else:
        run_cli_mode()
