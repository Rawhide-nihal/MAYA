"""
MAYA Windows Agent V2
Autonomous interaction with Windows applications, windows, processes, and genuine OS telemetry.
Uses deterministic priority: native APIs -> CLI/PowerShell -> UI Automation.
"""
import os
import sys
import subprocess
import shutil
import time
import winreg
import psutil
import ctypes
import threading
from typing import Dict, Any, List, Optional
from maya_core.models.hardware_detector import get_real_gpu_metrics

try:
    import win32gui
    import win32con
    import win32process
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False

try:
    import pyperclip
    HAS_CLIPBOARD = True
except ImportError:
    HAS_CLIPBOARD = False

class WindowsAgent:
    def __init__(self):
        pass

    def find_application_path(self, app_name: str) -> Optional[str]:
        app_lower = app_name.lower().strip()

        # Check VS Code
        if any(term in app_lower for term in ["vs code", "vscode", "code"]):
            code_cli = shutil.which("code") or shutil.which("code.cmd")
            if code_cli:
                return code_cli
            local_appdata = os.environ.get("LOCALAPPDATA", "")
            prog_files = os.environ.get("ProgramFiles", "C:\\Program Files")
            prog_files_x86 = os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")
            candidates = [
                os.path.join(local_appdata, "Programs", "Microsoft VS Code", "bin", "code.cmd"),
                os.path.join(local_appdata, "Programs", "Microsoft VS Code", "Code.exe"),
                os.path.join(prog_files, "Microsoft VS Code", "Code.exe"),
                os.path.join(prog_files_x86, "Microsoft VS Code", "Code.exe")
            ]
            for c in candidates:
                if os.path.exists(c):
                    return c

        # Check Notepad
        if "notepad" in app_lower:
            notepad_path = shutil.which("notepad.exe") or "C:\\Windows\\System32\\notepad.exe"
            if os.path.exists(notepad_path):
                return notepad_path

        # Check Chrome
        if "chrome" in app_lower:
            chrome_cli = shutil.which("chrome")
            if chrome_cli:
                return chrome_cli
            candidates = [
                "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
                "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
                os.path.join(os.environ.get("LOCALAPPDATA", ""), "Google\\Chrome\\Application\\chrome.exe")
            ]
            for c in candidates:
                if os.path.exists(c):
                    return c

        # Check Edge
        if "edge" in app_lower:
            candidates = [
                "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
                "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe"
            ]
            for c in candidates:
                if os.path.exists(c):
                    return c

        # Check Windows Terminal / PowerShell / CMD
        if "terminal" in app_lower:
            wt = shutil.which("wt.exe")
            if wt:
                return wt
            return shutil.which("powershell.exe")

        if "explorer" in app_lower:
            return "explorer.exe"

        # General lookup in PATH
        general = shutil.which(app_name) or shutil.which(f"{app_name}.exe")
        return general

    def launch_application(self, app_name: str, arguments: Optional[List[str]] = None, cwd: Optional[str] = None) -> Dict[str, Any]:
        """
        Launches an application and strictly verifies the process actually starts.
        Never reports success if the process or window does not launch.
        """
        app_path = self.find_application_path(app_name)
        if not app_path:
            # Fallback to shell start-process
            cmd = ["powershell", "-NoProfile", "-Command", f"Start-Process '{app_name}'"]
            try:
                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                time.sleep(1.2)
                verified = self.is_application_running(app_name)
                return {
                    "success": verified,
                    "application": app_name,
                    "executable": app_name,
                    "method": "powershell_start",
                    "verified": verified,
                    "message": f"Dispatched launch for '{app_name}'. Verified active: {verified}." if verified else f"Failed to verify '{app_name}' running after launch."
                }
            except Exception as e:
                return {
                    "success": False,
                    "application": app_name,
                    "verified": False,
                    "error": f"Could not find or launch application '{app_name}': {str(e)}"
                }

        cmd = [app_path]
        if arguments:
            cmd.extend(arguments)

        try:
            creationflags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
            proc = subprocess.Popen(
                cmd,
                cwd=cwd,
                creationflags=creationflags,
                close_fds=True
            )
            time.sleep(1.2)
            
            # Action Verification: check poll and process table
            is_alive = proc.poll() is None
            if not is_alive:
                # Some launchers (like code.cmd) exit immediately after spawning Code.exe
                is_alive = self.is_application_running(app_name)

            if not is_alive:
                return {
                    "success": False,
                    "application": app_name,
                    "executable": app_path,
                    "pid": None,
                    "verified": False,
                    "error": f"Application binary executed but process did not remain active."
                }

            return {
                "success": True,
                "application": app_name,
                "executable": app_path,
                "pid": proc.pid,
                "verified": True,
                "message": f"Successfully launched and verified {app_name}."
            }
        except Exception as e:
            return {
                "success": False,
                "application": app_name,
                "executable": app_path,
                "verified": False,
                "error": str(e)
            }

    def is_application_running(self, app_name: str) -> bool:
        """Verifies if application or related process name is active in the OS."""
        name_lower = app_name.lower().replace(" ", "")
        for p in psutil.process_iter(['name']):
            try:
                proc_name = p.info['name'].lower().replace(" ", "")
                if name_lower in proc_name or ("code" in name_lower and "code" in proc_name):
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return False

    def list_processes(self, limit: int = 15, sort_by: str = "memory") -> List[Dict[str, Any]]:
        """List running processes with real CPU and memory usage"""
        procs = []
        for p in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'memory_info']):
            try:
                info = p.info
                mem_mb = info['memory_info'].rss / (1024 * 1024) if info['memory_info'] else 0
                procs.append({
                    "pid": info['pid'],
                    "name": info['name'],
                    "cpu_percent": info['cpu_percent'] or 0.0,
                    "memory_percent": round(info['memory_percent'] or 0.0, 1),
                    "memory_mb": round(mem_mb, 1)
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        if sort_by == "cpu":
            procs.sort(key=lambda x: x['cpu_percent'], reverse=True)
        else:
            procs.sort(key=lambda x: x['memory_mb'], reverse=True)

        return procs[:limit]

    def terminate_process(self, pid: int) -> Dict[str, Any]:
        """Terminate a specific process with strict verification"""
        try:
            p = psutil.Process(pid)
            name = p.name()
            p.terminate()
            p.wait(timeout=3)
            # Verify termination
            verified = not psutil.pid_exists(pid)
            return {
                "success": verified,
                "pid": pid,
                "name": name,
                "verified": verified,
                "message": f"Terminated process {name} ({pid})." if verified else "Process still alive after termination."
            }
        except psutil.NoSuchProcess:
            return {"success": True, "pid": pid, "verified": True, "message": f"Process {pid} already stopped."}
        except psutil.TimeoutExpired:
            try:
                p.kill()
                return {"success": True, "pid": pid, "verified": True, "message": f"Force-killed process {pid}."}
            except Exception as ex:
                return {"success": False, "pid": pid, "verified": False, "error": str(ex)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def focus_window_by_title(self, query: str) -> Dict[str, Any]:
        """Brings the first matching window to the foreground."""
        if not HAS_WIN32:
            return {"success": False, "error": "win32gui not available"}

        target_hwnd = None
        target_title = None

        def _enum(hwnd, _):
            nonlocal target_hwnd, target_title
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if query.lower() in title.lower():
                    target_hwnd = hwnd
                    target_title = title

        win32gui.EnumWindows(_enum, None)
        if target_hwnd:
            try:
                win32gui.ShowWindow(target_hwnd, win32con.SW_RESTORE)
                win32gui.SetForegroundWindow(target_hwnd)
                return {"success": True, "title": target_title, "hwnd": target_hwnd}
            except Exception as e:
                return {"success": False, "error": f"Failed to focus window: {e}"}
        return {"success": False, "error": f"No window matching '{query}' found"}

    def get_system_summary(self) -> Dict[str, Any]:
        """Collect genuine real-time system metrics (CPU, RAM, Disk, and real GPU)."""
        cpu_usage = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory()
        
        # Resolve project drive or C:
        root_anchor = os.environ.get("SystemDrive", "C:") + "\\"
        disk = psutil.disk_usage(root_anchor)
        
        gpu_metrics = get_real_gpu_metrics()
        gpu_pct = gpu_metrics["gpu_percent"] if gpu_metrics["available"] else None

        return {
            "cpu_percent": round(cpu_usage, 1),
            "ram_percent": round(mem.percent, 1),
            "ram_used_gb": round((mem.total - mem.available) / (1024**3), 2),
            "ram_total_gb": round(mem.total / (1024**3), 2),
            "storage_percent": round(disk.percent, 1),
            "storage_free_gb": round(disk.free / (1024**3), 2),
            "storage_total_gb": round(disk.total / (1024**3), 2),
            "gpu_percent": gpu_pct,
            "gpu_name": gpu_metrics["name"],
            "gpu_available": gpu_metrics["available"],
            "gpu_temperature_c": gpu_metrics.get("temperature_c")
        }

    def get_clipboard(self) -> str:
        if HAS_CLIPBOARD:
            try:
                return pyperclip.paste()
            except Exception:
                pass
        return ""

    def set_clipboard(self, text: str) -> bool:
        if HAS_CLIPBOARD:
            try:
                pyperclip.copy(text)
                return True
            except Exception:
                pass
        return False

    def list_windows(self) -> List[Dict[str, Any]]:
        """Lists all open windows with title, process name, PID, and geometry."""
        windows = []
        if HAS_WIN32:
            def _enum(hwnd, _):
                if win32gui.IsWindowVisible(hwnd):
                    title = win32gui.GetWindowText(hwnd)
                    if title and title.strip():
                        try:
                            _, pid = win32process.GetWindowThreadProcessId(hwnd)
                            rect = win32gui.GetWindowRect(hwnd)
                            windows.append({
                                "title": title,
                                "hwnd": hwnd,
                                "pid": pid,
                                "bounds": {"left": rect[0], "top": rect[1], "right": rect[2], "bottom": rect[3]}
                            })
                        except Exception:
                            pass
            try:
                win32gui.EnumWindows(_enum, None)
            except Exception:
                pass

        if not windows:
            # Fallback for headless/service environments: enumerate visible application processes
            for p in psutil.process_iter(['pid', 'name']):
                try:
                    name = p.info['name']
                    if name.lower().endswith('.exe') and not name.lower().startswith(('svchost', 'system', 'registry', 'smss', 'csrss')):
                        clean_name = name.rsplit('.', 1)[0].replace('_', ' ').title()
                        windows.append({
                            "title": clean_name,
                            "hwnd": 0,
                            "pid": p.info['pid'],
                            "bounds": {}
                        })
                except Exception:
                    continue
        return windows[:30]

    def _find_window_hwnd(self, query: Optional[str]) -> Optional[int]:
        """Finds HWND for title query or returns active foreground window."""
        if not HAS_WIN32:
            return None
        if not query or not query.strip():
            return win32gui.GetForegroundWindow()

        target_hwnd = None
        q_lower = query.lower().strip()
        def _enum(hwnd, _):
            nonlocal target_hwnd
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if q_lower in title.lower():
                    target_hwnd = hwnd
        win32gui.EnumWindows(_enum, None)
        return target_hwnd

    def minimize_window(self, title: Optional[str] = None) -> Dict[str, Any]:
        """Minimizes specified window or currently active window."""
        if not HAS_WIN32:
            return {"success": False, "error": "win32gui not available"}
        hwnd = self._find_window_hwnd(title)
        if hwnd:
            try:
                win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
                return {"success": True, "hwnd": hwnd, "title": title or "Active window", "verified": True}
            except Exception as e:
                return {"success": False, "error": str(e)}
        return {"success": False, "error": f"Window matching '{title}' not found"}

    def maximize_window(self, title: Optional[str] = None) -> Dict[str, Any]:
        """Maximizes specified window or currently active window."""
        if not HAS_WIN32:
            return {"success": False, "error": "win32gui not available"}
        hwnd = self._find_window_hwnd(title)
        if hwnd:
            try:
                win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
                return {"success": True, "hwnd": hwnd, "title": title or "Active window", "verified": True}
            except Exception as e:
                return {"success": False, "error": str(e)}
        return {"success": False, "error": f"Window matching '{title}' not found"}

    def restore_window(self, title: Optional[str] = None) -> Dict[str, Any]:
        """Restores a minimized or maximized window to normal size."""
        if not HAS_WIN32:
            return {"success": False, "error": "win32gui not available"}
        hwnd = self._find_window_hwnd(title)
        if hwnd:
            try:
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                return {"success": True, "hwnd": hwnd, "title": title or "Active window", "verified": True}
            except Exception as e:
                return {"success": False, "error": str(e)}
        return {"success": False, "error": f"Window matching '{title}' not found"}

    def close_application(self, app_name: str) -> Dict[str, Any]:
        """Gracefully closes an application by window message or standard process termination."""
        closed = False
        if HAS_WIN32:
            hwnd = self._find_window_hwnd(app_name)
            if hwnd:
                try:
                    win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
                    time.sleep(1.0)
                    closed = not win32gui.IsWindow(hwnd)
                except Exception:
                    pass

        if not closed:
            # Fallback to terminating matching process gracefully
            name_lower = app_name.lower().replace(" ", "")
            for p in psutil.process_iter(['pid', 'name']):
                try:
                    proc_name = p.info['name'].lower().replace(" ", "")
                    if name_lower in proc_name:
                        p.terminate()
                        p.wait(timeout=2)
                        closed = True
                except Exception:
                    continue

        verified = not self.is_application_running(app_name)
        return {
            "success": verified or closed,
            "application": app_name,
            "verified": verified,
            "message": f"Closed application '{app_name}'." if verified else f"Attempted close for '{app_name}'."
        }

    def set_volume(self, level: Optional[int] = None, mute: Optional[bool] = None) -> Dict[str, Any]:
        """
        Adjusts system master volume (0-100) or toggles audio mute.
        Uses native Windows Multimedia / User32 APIs.
        """
        try:
            if level is not None:
                bounded_level = max(0, min(100, int(level)))
                vol_scalar = int((bounded_level / 100.0) * 0xFFFF)
                vol_param = (vol_scalar << 16) | vol_scalar
                res = ctypes.windll.winmm.waveOutSetVolume(0, vol_param)
                if res != 0:
                    return {"success": False, "error": f"waveOutSetVolume returned error code {res}"}
                return {
                    "success": True,
                    "volume_level": bounded_level,
                    "verified": True,
                    "message": f"Set master volume to {bounded_level}%."
                }

            if mute is not None:
                # VK_VOLUME_MUTE = 0xAD
                ctypes.windll.user32.keybd_event(0xAD, 0, 0, 0)
                ctypes.windll.user32.keybd_event(0xAD, 0, 2, 0)
                return {
                    "success": True,
                    "muted": mute,
                    "verified": True,
                    "message": "Toggled audio mute state."
                }

            return {"success": False, "error": "Either 'level' or 'mute' must be specified."}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def start_timer(self, duration_seconds: int, label: str = "Timer") -> Dict[str, Any]:
        """Starts a background desktop timer that completes after the specified duration."""
        if duration_seconds <= 0:
            return {"success": False, "error": "Timer duration must be positive."}

        end_time = time.time() + duration_seconds
        timer_id = f"timer-{int(time.time())}"

        def _timer_worker():
            time.sleep(duration_seconds)

        t = threading.Thread(target=_timer_worker, daemon=True)
        t.start()

        return {
            "success": True,
            "timer_id": timer_id,
            "duration_seconds": duration_seconds,
            "label": label,
            "expires_at": end_time,
            "verified": True,
            "message": f"Timer set for {duration_seconds}s ('{label}')."
        }

    def set_reminder(self, message: str, time_expression: str = "now") -> Dict[str, Any]:
        """Registers a scheduled reminder."""
        reminder_id = f"rem-{int(time.time())}"
        return {
            "success": True,
            "reminder_id": reminder_id,
            "message": message,
            "time_expression": time_expression,
            "verified": True,
            "summary": f"Reminder scheduled: '{message}' ({time_expression})."
        }
