"""
MAYA Skills Registry
Defines extensible plugin architecture for MAYA skills.
"""
from typing import Dict, Any, List
from dataclasses import dataclass

@dataclass
class MayaSkill:
    id: str
    name: str
    version: str
    category: str
    description: str
    permission_level: int
    tools: List[str]
    enabled: bool = True

class SkillsRegistry:
    def __init__(self):
        self.skills: Dict[str, MayaSkill] = {}
        self._register_default_skills()

    def _register_default_skills(self):
        defaults = [
            MayaSkill(
                id="windows_control",
                name="Windows PC Control",
                version="1.0.0",
                category="System",
                description="Controls applications, processes, windows, and core Windows functions.",
                permission_level=2,
                tools=["open_application", "verify_application", "list_processes", "terminate_process"]
            ),
            MayaSkill(
                id="developer_tools",
                name="Developer Workspace",
                version="1.0.0",
                category="Development",
                description="Detects project ecosystems, build configurations, and inspects compiler/syntax issues.",
                permission_level=2,
                tools=["inspect_project", "build_project", "check_git_status"]
            ),
            MayaSkill(
                id="diagnostics",
                name="System Diagnostics",
                version="1.0.0",
                category="Diagnostics",
                description="Monitors CPU, RAM, disk health, network gateway, and defensive security state.",
                permission_level=1,
                tools=["run_system_diagnostics", "get_system_status"]
            ),
            MayaSkill(
                id="filesystem",
                name="Filesystem Manager",
                version="1.0.0",
                category="Storage",
                description="Deep search, file content inspection, directory organization, and safe cleanup.",
                permission_level=3,
                tools=["search_files", "read_file", "write_file", "move_file", "clean_temp_files"]
            ),
            MayaSkill(
                id="vision",
                name="Screen & Window Vision",
                version="1.0.0",
                category="Vision",
                description="Captures display screens and inspects active application window coordinates.",
                permission_level=1,
                tools=["capture_screen", "detect_windows"]
            )
        ]
        for s in defaults:
            self.skills[s.id] = s

    def list_skills(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": s.id,
                "name": s.name,
                "version": s.version,
                "category": s.category,
                "description": s.description,
                "permission_level": s.permission_level,
                "tools": s.tools,
                "enabled": s.enabled
            } for s in self.skills.values()
        ]
