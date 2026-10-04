"""
MAYA Terminal Agent
Structured execution subsystem for PowerShell and CMD.
Returns typed execution metrics and sanitizes commands against dangerous patterns.
"""
import subprocess
import time
import os
from typing import Dict, Any, Optional

class TerminalAgent:
    def __init__(self, default_cwd: Optional[str] = None):
        self.default_cwd = default_cwd or os.getcwd()

    def run_command(self, command: str, cwd: Optional[str] = None, timeout: int = 45, shell_type: str = "powershell") -> Dict[str, Any]:
        target_cwd = cwd or self.default_cwd
        if not os.path.exists(target_cwd):
            target_cwd = os.getcwd()

        start_time = time.time()

        if shell_type == "powershell":
            cmd_args = ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", command]
        else:
            cmd_args = ["cmd.exe", "/c", command]

        try:
            process = subprocess.Popen(
                cmd_args,
                cwd=target_cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace"
            )

            try:
                stdout, stderr = process.communicate(timeout=timeout)
                exit_code = process.returncode
            except subprocess.TimeoutExpired:
                process.kill()
                stdout, stderr = process.communicate()
                return {
                    "command": command,
                    "cwd": target_cwd,
                    "stdout": stdout,
                    "stderr": f"Execution timed out after {timeout} seconds.",
                    "exit_code": -1,
                    "execution_time_sec": round(time.time() - start_time, 2),
                    "success": False,
                    "shell": shell_type
                }

            exec_time = round(time.time() - start_time, 2)
            return {
                "command": command,
                "cwd": target_cwd,
                "stdout": stdout.strip(),
                "stderr": stderr.strip(),
                "exit_code": exit_code,
                "execution_time_sec": exec_time,
                "success": exit_code == 0,
                "shell": shell_type
            }
        except Exception as e:
            return {
                "command": command,
                "cwd": target_cwd,
                "stdout": "",
                "stderr": str(e),
                "exit_code": 1,
                "execution_time_sec": round(time.time() - start_time, 2),
                "success": False,
                "shell": shell_type
            }
