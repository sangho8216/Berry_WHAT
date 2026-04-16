import sys
from core.logic import SystemControl
from interface.collector import DataCollector

def main():
    print("Initializing Berry_WHAT System...")
    collector = DataCollector()
    engine = SystemControl()
    
    try:
        # Main system loop
        while True:
            data = collector.collect_signals()
            engine.process(data)
    except KeyboardInterrupt:
        print("\nShutting down Berry_WHAT.")
        sys.exit(0)

if __name__ == "__main__":
    main()
