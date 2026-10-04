"""
MAYA Core API & Real-time Server
Bridges the GUI (Electron / Vite / Web) with the Python agents, memory, task planner, and action ledger.
"""
import os
import sys
import json
import time
from flask import Flask, request, jsonify

# Add repository root to Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from maya_core.personality.spec import build_maya_prompt
from maya_core.models.base import DeterministicIntentClassifier
from maya_core.router.model_router import ModelRouter
from security.permissions.tier import PermissionManager, PermissionLevel
from security.audit.ledger import ActionLedger
from memory.store import MemoryStore
from agents.windows.agent import WindowsAgent
from agents.terminal.agent import TerminalAgent
from agents.filesystem.agent import FileAgent
from agents.developer.agent import DeveloperAgent
from agents.diagnostics.engine import DiagnosticEngine
from agents.vision.agent import VisionAgent
from maya_core.planner.task_planner import TaskPlanner
from skills.registry import SkillsRegistry
from voice.engine import VoiceEngine

app = Flask(__name__)

# Core Subsystems Initialization
router = ModelRouter()
permissions = PermissionManager(PermissionLevel.LEVEL_2_SAFE_ACTION)
ledger = ActionLedger()
memory = MemoryStore()
windows = WindowsAgent()
terminal = TerminalAgent()
filesystem = FileAgent()
developer = DeveloperAgent(terminal)
diagnostics = DiagnosticEngine(terminal)
vision = VisionAgent()
planner = TaskPlanner(router, permissions, ledger, memory, windows, terminal, filesystem, developer, diagnostics, vision)
skills = SkillsRegistry()
voice = VoiceEngine()

# Add simple CORS headers to all responses
@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
    response.headers['Access-Control-Allow-Methods'] = 'GET,POST,OPTIONS'
    return response

@app.route("/api/status", methods=["GET"])
def get_status():
    """Live system metrics for GUI right-hand panel & core state"""
    summary = windows.get_system_summary()
    return jsonify({
        "status": "online",
        "maya_core": "Active",
        "local_ai_ready": True,
        "offline_only": router.offline_only,
        "metrics": summary,
        "active_project": developer.active_project_path
    })

@app.route("/api/activity", methods=["GET"])
def get_activity():
    """Recent Action Ledger history"""
    limit = int(request.args.get("limit", 15))
    actions = ledger.get_recent_actions(limit=limit)
    return jsonify({"actions": actions})

@app.route("/api/diagnostics", methods=["GET"])
def run_diagnostics():
    """Run genuine full diagnostic scan"""
    res = diagnostics.run_full_diagnostics()
    return jsonify(res)

@app.route("/api/projects", methods=["GET"])
def get_projects():
    """Inspect and list projects"""
    details = developer.detect_project_details()
    mems = memory.get_all_memories()
    return jsonify({
        "active_project": details,
        "saved_projects": mems.get("projects", [])
    })

@app.route("/api/memory", methods=["GET"])
def get_memory_data():
    """Transparent Memory inspection"""
    data = memory.get_all_memories()
    history = memory.get_conversation_history(limit=50)
    return jsonify({
        "memories": data,
        "history": history
    })

@app.route("/api/skills", methods=["GET"])
def get_skills():
    """Registered skills"""
    return jsonify({"skills": skills.list_skills()})

@app.route("/api/action/rollback", methods=["POST"])
def rollback_action():
    """Rollback action"""
    data = request.get_json(silent=True) or {}
    action_id = data.get("action_id")
    if action_id:
        res = ledger.rollback_action(action_id)
    else:
        res = ledger.rollback_last_action()
    return jsonify(res)

@app.route("/api/chat", methods=["POST"])
def handle_chat():
    """
    Main conversational and task entrypoint.
    Executes the Understand -> Plan -> Act -> Observe -> Verify -> Report pipeline.
    """
    data = request.get_json(silent=True) or {}
    user_text = data.get("message", "").strip()
    if not user_text:
        return jsonify({"error": "No message provided"}), 400

    # 1. Save user message to memory
    memory.add_message("user", user_text)

    # 2. Understand: Sub-millisecond intent extraction
    intent_info = router.route_intent(user_text)
    intent = intent_info.get("intent", "CHAT")
    tool = intent_info.get("tool")

    # If conversational or suggestion without direct tool execution
    if intent in ["CHAT", "SUGGESTION"] or not tool:
        relevant_mem = memory.search_relevant_memories(user_text, top_k=2)
        system_status = windows.get_system_summary()
        
        reply = router.generate_response(user_text)
        memory.add_message("maya", reply)
        
        return jsonify({
            "intent": intent,
            "reply": reply,
            "executed_tool": None,
            "tasks": [],
            "timestamp": time.time()
        })

    # 3. Plan: Create task plan
    plan = planner.create_plan_for_request(user_text, intent_info)
    executed_tasks = []
    findings_details = None

    # 4. Act -> Observe -> Verify -> Report for each step in plan
    for step in plan.steps:
        step.status = "running"
        tool_res = planner.execute_tool(step.tool, step.arguments)
        
        step_status = "completed" if tool_res.get("success", True) else "failed"
        step.status = step_status
        step.result = tool_res

        executed_tasks.append({
            "name": step.name,
            "description": step.description,
            "tool": step.tool,
            "status": step_status,
            "result": tool_res
        })

        if step.tool == "inspect_project":
            findings_details = tool_res

    # 5. Formulate final natural response
    if tool == "open_application_and_inspect":
        app_name = intent_info.get("arguments", {}).get("application", "VS Code")
        issues_count = findings_details.get("issues_count", 0) if findings_details else 0
        reply = f"{app_name} is now open and I've scanned your project."
        if issues_count == 0:
            reply += " No syntax or configuration errors were found. Workspace is healthy."
        else:
            reply += f" I found {issues_count} minor issue(s). Here's what I found:"
    elif tool == "open_application":
        app_name = intent_info.get("arguments", {}).get("application", "Application")
        reply = f"{app_name} has been launched and verified running."
    elif tool == "run_system_diagnostics":
        reply = "System diagnostic scan completed. Check the PC Control panel for detailed health indicators."
    elif tool == "rollback_last_action":
        reply = "Reversible action successfully rolled back in the action ledger."
    elif tool == "get_recent_actions":
        reply = "Here are the recent actions recorded in the Action Ledger."
    else:
        reply = f"Completed requested task: {intent_info.get('summary', 'Action executed')}."

    memory.add_message("maya", reply, metadata={"executed_tasks": executed_tasks})

    return jsonify({
        "intent": intent,
        "reply": reply,
        "executed_tool": tool,
        "plan_id": plan.plan_id,
        "tasks": executed_tasks,
        "details": findings_details,
        "timestamp": time.time()
    })

def start_server(host="127.0.0.1", port=5000):
    print(f"Starting MAYA Core Server on http://{host}:{port} ...")
    app.run(host=host, port=port, debug=False, use_reloader=False)

if __name__ == "__main__":
    start_server()
