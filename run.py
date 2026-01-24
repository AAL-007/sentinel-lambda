"""
SENTINEL-Λ: Unified Research Launcher
Usage: python run.py
"""

import subprocess
import sys
import time
import os

# -------------------------------------------------
# Configuration
# -------------------------------------------------
API_HOST = "127.0.0.1"
API_PORT = "8001"
DASHBOARD_PORT = "8501"

# Global flag for the main loop
running = True

def start_api():
    print(f"🚀 Initializing Safety Engine (API) on {API_HOST}:{API_PORT}...")
    # We run as a module (-m) to resolve relative imports in src/
    return subprocess.Popen(
        [
            sys.executable, "-m", "uvicorn", 
            "src.api.server:app", 
            "--host", API_HOST, 
            "--port", API_PORT
        ]
    )

def start_dashboard():
    # Wait briefly for API to spin up
    time.sleep(2) 
    print(f"📊 Launching Governance Console (Dashboard) on {API_HOST}:{DASHBOARD_PORT}...")
    
    # Set env var explicitly for local run using config constants
    env = os.environ.copy()
    env["SENTINEL_API_URL"] = f"http://{API_HOST}:{API_PORT}/evaluate"
    
    return subprocess.Popen(
        [
            sys.executable, "-m", "streamlit", "run", 
            "src/dashboard/app.py",
            "--server.port", DASHBOARD_PORT,
            "--server.address", API_HOST  # <--- Symmetrical usage
        ],
        env=env
    )

def main():
    global running
    print("--- SENTINEL-Λ RESEARCH ENVIRONMENT ---")
    print("Press Ctrl+C to stop all services.")
    print("---------------------------------------")

    api_process = start_api()
    dash_process = start_dashboard()

    try:
        while running:
            # Check if processes are alive
            if api_process.poll() is not None:
                print("❌ API Process died unexpectedly.")
                running = False
            if dash_process.poll() is not None:
                print("❌ Dashboard Process died unexpectedly.")
                running = False
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Shutting down SENTINEL-Λ...")
    finally:
        # Graceful cleanup
        if api_process.poll() is None:
            api_process.terminate()
        if dash_process.poll() is None:
            dash_process.terminate()
        print("✅ Services stopped.")

if __name__ == "__main__":
    main()