"""
MAYA Desktop Companion - Master Production Launcher
Starts the core Python API backend and opens the desktop GUI matching the reference UI.
"""
import os
import sys
import subprocess
import time
import urllib.request

def is_server_running(url="http://127.0.0.1:5000/api/status"):
    try:
        with urllib.request.urlopen(url, timeout=1.5) as resp:
            return resp.status == 200
    except Exception:
        return False

def main():
    root_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(root_dir)

    print("=" * 60)
    print("MAYA — PERSONAL AI DESKTOP COMPANION")
    print("Production Desktop Launcher")
    print("=" * 60)

    # 1. Start Maya API Server if not already active
    if not is_server_running():
        print("[1/2] Starting MAYA Core API Server (Python/Flask)...")
        server_cmd = [sys.executable, os.path.join(root_dir, "maya_server.py")]
        server_proc = subprocess.Popen(
            server_cmd,
            cwd=root_dir,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
        )
        # Wait for server to become responsive
        retries = 15
        while retries > 0 and not is_server_running():
            time.sleep(0.6)
            retries -= 1
        if is_server_running():
            print("      MAYA Core Server is ONLINE at http://127.0.0.1:5000")
        else:
            print("      [Warning] Server took longer than expected to report status.")
    else:
        print("[1/2] MAYA Core Server is already running.")

    # 2. Launch Desktop GUI Window
    print("[2/2] Launching MAYA Desktop Companion Window...")
    
    # Check for Electron or PyQt6
    dist_path = os.path.join(root_dir, "apps", "desktop", "dist", "index.html")
    if not os.path.exists(dist_path):
        print("      Building desktop frontend...")
        subprocess.run(["npm", "run", "build"], cwd=os.path.join(root_dir, "apps", "desktop"), shell=True)

    # Launch via Electron
    print("      Opening Electron Desktop Frame...")
    electron_bin = os.path.join(root_dir, "apps", "desktop", "node_modules", ".bin", "electron.cmd")
    if os.path.exists(electron_bin):
        electron_cmd = [electron_bin, "."]
    else:
        electron_cmd = ["npm", "--prefix", "apps/desktop", "run", "electron:dev"]
    
    subprocess.Popen(electron_cmd, cwd=os.path.join(root_dir, "apps", "desktop"), shell=True)
    print("MAYA Desktop Companion launched successfully.")

if __name__ == "__main__":
    main()
