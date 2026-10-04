"""
MAYA System Diagnostic Engine V2
Genuine deep scans across hardware, OS, performance, storage, processes, network, GPU, and dev tools.
Prioritizes findings into Healthy, Information, Recommendation, Warning, and Critical.
Zero fake metrics.
"""
import platform
import psutil
import shutil
import time
import os
from typing import Dict, Any, List
from agents.terminal.agent import TerminalAgent
from maya_core.models.hardware_detector import get_real_gpu_metrics

class DiagnosticEngine:
    def __init__(self, terminal: TerminalAgent = None):
        self.terminal = terminal or TerminalAgent()

    def run_full_diagnostics(self) -> Dict[str, Any]:
        findings = []
        
        # 1. System info
        uname = platform.uname()
        boot_time = psutil.boot_time()
        uptime_hours = round((time.time() - boot_time) / 3600, 1)

        # 2. CPU & RAM
        cpu_pct = psutil.cpu_percent(interval=0.2)
        cpu_count = psutil.cpu_count(logical=True)
        mem = psutil.virtual_memory()
        mem_pct = mem.percent

        if cpu_pct > 85.0:
            findings.append({
                "category": "Performance",
                "severity": "Warning",
                "message": f"High CPU utilization: {cpu_pct}% across {cpu_count} logical threads."
            })
        elif cpu_pct > 60.0:
            findings.append({
                "category": "Performance",
                "severity": "Information",
                "message": f"Moderate CPU utilization: {cpu_pct}%."
            })
        else:
            findings.append({
                "category": "Performance",
                "severity": "Healthy",
                "message": f"CPU utilization nominal: {cpu_pct}%."
            })

        if mem_pct > 85.0:
            findings.append({
                "category": "Performance",
                "severity": "Warning",
                "message": f"High RAM usage: {mem_pct}% ({round(mem.used / 1024**3, 1)} GB / {round(mem.total / 1024**3, 1)} GB)."
            })
        else:
            findings.append({
                "category": "Performance",
                "severity": "Healthy",
                "message": f"RAM usage nominal: {mem_pct}% ({round(mem.available / 1024**3, 1)} GB available)."
            })

        # 3. GPU Telemetry
        gpu = get_real_gpu_metrics()
        if gpu["available"]:
            gpu_pct = gpu["gpu_percent"]
            findings.append({
                "category": "Hardware",
                "severity": "Healthy",
                "message": f"GPU: {gpu['name']} ({gpu['vram_free_mb']} MB VRAM free, {gpu['temperature_c']}°C, {gpu_pct}% load)."
            })
        else:
            findings.append({
                "category": "Hardware",
                "severity": "Information",
                "message": "Dedicated NVIDIA GPU metrics unavailable or integrated graphics in use."
            })

        # 4. Storage
        sys_drive = os.environ.get("SystemDrive", "C:") + "\\"
        disk = psutil.disk_usage(sys_drive)
        disk_free_gb = round(disk.free / (1024**3), 1)
        if disk_free_gb < 15.0:
            findings.append({
                "category": "Storage",
                "severity": "Critical" if disk_free_gb < 5.0 else "Warning",
                "message": f"Low disk space on {sys_drive} only {disk_free_gb} GB free."
            })
        else:
            findings.append({
                "category": "Storage",
                "severity": "Healthy",
                "message": f"Drive {sys_drive} has {disk_free_gb} GB free ({round(disk.percent, 1)}% used)."
            })

        # 5. Dev Tools Verification
        tools = ["git", "node", "npm", "python", "code", "cargo"]
        installed_tools = {}
        for t in tools:
            path = shutil.which(t)
            if path:
                res = self.terminal.run_command(f"{t} --version", timeout=3)
                v_str = res["stdout"].split("\n")[0] if res["success"] and res["stdout"] else "Installed"
                installed_tools[t] = v_str
            else:
                installed_tools[t] = "Not found"

        # 6. Network connectivity
        ping_res = self.terminal.run_command("ping -n 1 8.8.8.8", timeout=3)
        net_connected = ping_res["success"] and "TTL=" in ping_res["stdout"]
        if not net_connected:
            findings.append({
                "category": "Networking",
                "severity": "Warning",
                "message": "Internet gateway connectivity check failed or timed out."
            })
        else:
            findings.append({
                "category": "Networking",
                "severity": "Healthy",
                "message": "Internet gateway connectivity verified."
            })

        # Overall Status
        has_critical = any(f["severity"] == "Critical" for f in findings)
        has_warning = any(f["severity"] == "Warning" for f in findings)
        overall_status = "Critical" if has_critical else ("Warning" if has_warning else "Healthy")

        severity_order = {"Critical": 0, "Warning": 1, "Recommendation": 2, "Information": 3, "Healthy": 4}
        findings.sort(key=lambda x: severity_order.get(x["severity"], 5))

        return {
            "status": overall_status,
            "timestamp": time.time(),
            "uptime_hours": uptime_hours,
            "metrics": {
                "cpu_percent": cpu_pct,
                "ram_percent": mem_pct,
                "storage_percent": round(disk.percent, 1),
                "gpu_percent": gpu["gpu_percent"] if gpu["available"] else None,
                "gpu_name": gpu["name"]
            },
            "system": {
                "os": f"{uname.system} {uname.release}",
                "architecture": uname.machine,
                "processor": uname.processor
            },
            "dev_tools": installed_tools,
            "findings": findings,
            "summary": f"System scan complete: {len(findings)} findings categorized. Health status is {overall_status}."
        }
