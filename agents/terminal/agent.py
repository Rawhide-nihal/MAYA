"""
MAYA Terminal Agent V2
Secure, policy-validated command execution subsystem for PowerShell and CMD.
Prevents dangerous command injection, arbitrary privilege escalation, and destructive commands.
"""
import subprocess
import time
import re
from pathlib import Path
from typing import Dict, Any, Optional, List
from maya_core.config import PROJECT_ROOT

class TerminalSecurityError(Exception):
    pass

class TerminalAgent:
    BLOCKED_PATTERNS = [
        r"\bformat\s+[a-zA-Z]:",
        r"\brmdir\s+/[sS]\s+[cC]:\\",
        r"\bdel\s+/[fFqQsS]\s+[cC]:\\Windows",
        r"\bRemove-Item\s+.*-Recurse\s+.*[cC]:\\Windows",
        r"\breg\s+delete\s+HKLM",
        r"\bSet-MpPreference\s+-DisableRealtimeMonitoring\s+\$true",
        r"\bnet\s+user\s+.*\/add",
        r"\bdiskpart\b",
        r"\bcd\s+.*&&.*format\b"
    ]

    def __init__(self, default_cwd: Optional[Path] = None):
        self.default_cwd = default_cwd or PROJECT_ROOT

    def validate_command_safety(self, command: str) -> None:
        """Enforces security boundaries against destructive or unprompted system alteration."""
        cmd_clean = command.strip()
        for pat in self.BLOCKED_PATTERNS:
            if re.search(pat, cmd_clean, re.IGNORECASE):
                raise TerminalSecurityError(f"Command blocked by Terminal Security Policy: matched high-risk pattern '{pat}'")

    def run_command(
        self,
        command: str,
        cwd: Optional[str] = None,
        timeout: int = 45,
        shell_type: str = "powershell"
    ) -> Dict[str, Any]:
        target_cwd = Path(cwd).resolve() if cwd else self.default_cwd
        if not target_cwd.exists():
            target_cwd = PROJECT_ROOT

        start_time = time.time()

        try:
            self.validate_command_safety(command)
        except TerminalSecurityError as err:
            return {
                "command": command,
                "cwd": str(target_cwd),
                "stdout": "",
                "stderr": str(err),
                "exit_code": 403,
                "execution_time_sec": 0.0,
                "success": False,
                "shell": shell_type,
                "security_blocked": True
            }

        if shell_type == "powershell":
            cmd_args = [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy", "Bypass",
                "-Command", command
            ]
        else:
            cmd_args = ["cmd.exe", "/c", command]

        try:
            process = subprocess.Popen(
                cmd_args,
                cwd=str(target_cwd),
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
                    "cwd": str(target_cwd),
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
                "cwd": str(target_cwd),
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
                "cwd": str(target_cwd),
                "stdout": "",
                "stderr": str(e),
                "exit_code": 1,
                "execution_time_sec": round(time.time() - start_time, 2),
                "success": False,
                "shell": shell_type
            }
