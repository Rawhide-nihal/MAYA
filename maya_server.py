"""
MAYA Core API & Real-time Event Bus Server V2
Secure localhost API with session token authentication, Server-Sent Events (SSE) event bus,
model management, streaming inference, and dynamic task orchestration.
Zero fake metrics. Zero unrestricted CORS.
"""
import os
import sys
import json
import time
import queue
import threading
import hmac
import base64
from urllib.parse import urlparse
from pathlib import Path
from flask import Flask, request, jsonify, Response, stream_with_context, send_file
from werkzeug.utils import secure_filename

# Add repository root to Python path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from maya_core.config import settings, AUTH_TOKEN, PROJECT_ROOT
from maya_core.models.runtime import model_runtime
from maya_core.models.hardware_detector import get_real_gpu_metrics, get_hardware_profile
from security.permissions.tier import PermissionManager, PermissionLevel
from security.audit.ledger import ActionLedger
from memory.store import MemoryStore
from agents.windows.agent import WindowsAgent
from agents.terminal.agent import TerminalAgent
from agents.filesystem.agent import FileAgent
from agents.developer.agent import DeveloperAgent
from agents.diagnostics.engine import DiagnosticEngine
from agents.vision.agent import VisionAgent
from agents.browser.agent import BrowserAgent
from agents.communication.agent import CommunicationAgent
from agents.communication.bridge import communication_bridge
from maya_core.context.builder import ContextBuilder
from maya_core.context.engine import UnifiedContextEngine
from maya_core.personality.engine import PersonalityEngine
from maya_core.attachments.intelligence import AttachmentIntelligence
from maya_core.planner.dynamic_planner import DynamicTaskPlanner
from maya_core.brain.brain import MayaBrain
from skills.registry import SkillsRegistry
from voice.engine import VoiceEngine, calculate_pcm_rms
from maya_core.events import (
    MAYA_STATE_CHANGED,
    PERMISSION_RESOLVED,
    ACTION_ROLLED_BACK,
    VOICE_LISTENING_AMPLITUDE,
)

app = Flask(__name__)

# Real-time Event Bus Queue
event_subscribers = []
event_lock = threading.Lock()

def dispatch_event(event_name: str, payload: dict):
    """Broadcasts event to all active SSE subscribers."""
    with event_lock:
        data_str = json.dumps({"event": event_name, "data": payload, "timestamp": time.time()})
        for q in list(event_subscribers):
            try:
                q.put_nowait(data_str)
            except Exception:
                pass

# Subsystems Initialization
perm_level = PermissionLevel(settings.get("permission_level", 2))
permissions = PermissionManager(perm_level)
ledger = ActionLedger()
memory = MemoryStore()
windows = WindowsAgent()
terminal = TerminalAgent()
filesystem = FileAgent()
developer = DeveloperAgent(terminal)
diagnostics = DiagnosticEngine(terminal)
vision = VisionAgent()
browser = BrowserAgent()
communication = CommunicationAgent(windows=windows, bridge=communication_bridge)
personality = PersonalityEngine()
unified_context = UnifiedContextEngine(
    windows=windows,
    vision=vision,
    memory=memory,
    ledger=ledger,
    browser_context_source=communication_bridge
)
attachment_intelligence = AttachmentIntelligence()

planner = DynamicTaskPlanner(
    permissions, ledger, memory, windows, terminal, filesystem,
    developer, diagnostics, vision, browser,
    communication=communication,
    unified_context=unified_context,
    event_callback=dispatch_event
)

voice = VoiceEngine(event_emitter=dispatch_event)
context_builder = ContextBuilder(
    memory, ledger, windows, developer,
    unified_context=unified_context,
    personality=personality
)
brain = MayaBrain(
    context_builder, planner, memory, permissions, ledger,
    runtime=model_runtime,
    unified_context=unified_context,
    personality=personality
)
skills = SkillsRegistry()

# Security & Origin Validation
ALLOWED_ORIGIN_HOSTS = {"127.0.0.1", "localhost", "null"}
ALLOWED_EXACT_ORIGINS = {
    "http://127.0.0.1:5173",
    "http://localhost:5173",
    "vscode-webview://",
    "app://maya",
    "chrome-extension://cbffklcgjeagclgldpkiflcbgbmjgohh",
    "null"
}

@app.before_request
def validate_request_security():
    # Allow OPTIONS preflight
    if request.method == "OPTIONS":
        return

    # Host validation (loopback only)
    host = request.headers.get("Host", "").split(":")[0]
    if host not in ALLOWED_ORIGIN_HOSTS:
        return jsonify({"error": "Forbidden: Untrusted host"}), 403

    # Strict Origin validation when Origin header is present
    origin = request.headers.get("Origin", "")
    if origin:
        parsed_origin = urlparse(origin)
        origin_host = parsed_origin.hostname or origin
        if origin_host not in ALLOWED_ORIGIN_HOSTS and origin not in ALLOWED_EXACT_ORIGINS:
            return jsonify({"error": "Forbidden: Untrusted origin"}), 403

    # Mandatory Session Token Check for all state-changing endpoints
    STATE_CHANGING_METHODS = {"POST", "PUT", "DELETE", "PATCH"}
    if request.method in STATE_CHANGING_METHODS:
        req_token = request.headers.get("X-Maya-Token", "").strip()
        if not req_token:
            return jsonify({"error": "Unauthorized: Missing X-Maya-Token session header"}), 401
        if not hmac.compare_digest(req_token, AUTH_TOKEN):
            return jsonify({"error": "Unauthorized: Invalid session token"}), 401

@app.after_request
def apply_secure_cors(response):
    origin = request.headers.get("Origin", "")
    if origin:
        parsed_origin = urlparse(origin)
        origin_host = parsed_origin.hostname or origin
        if origin_host in ALLOWED_ORIGIN_HOSTS or origin in ALLOWED_EXACT_ORIGINS:
            response.headers['Access-Control-Allow-Origin'] = origin
    else:
        response.headers['Access-Control-Allow-Origin'] = 'http://127.0.0.1:5173'

    response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization,X-Maya-Token'
    response.headers['Access-Control-Allow-Methods'] = 'GET,POST,OPTIONS'
    return response

# 1. Real-Time SSE Event Stream
@app.route("/api/events", methods=["GET"])
def event_stream():
    """Server-Sent Events endpoint broadcasting live Maya state, task progression, and audio amplitude."""
    def gen():
        q = queue.Queue(maxsize=100)
        with event_lock:
            event_subscribers.append(q)
        try:
            # Send initial connection event WITHOUT privileged token leak
            yield f"data: {json.dumps({'event': 'connected', 'status': 'ready'})}\n\n"
            while True:
                msg = q.get()
                yield f"data: {msg}\n\n"
        except GeneratorExit:
            with event_lock:
                if q in event_subscribers:
                    event_subscribers.remove(q)

    return Response(gen(), mimetype="text/event-stream")

# 2. Status & Metrics (Zero fake metrics)
@app.route("/api/status", methods=["GET"])
def get_status():
    summary = windows.get_system_summary()
    model_info = model_runtime.get_status()
    return jsonify({
        "status": "online",
        "maya_core": "Active",
        "local_ai_ready": model_info.get("lifecycle_state") == "READY",
        "offline_only": settings.get("offline_only", True),
        "metrics": summary,
        "model": model_info,
        "active_project": str(developer.active_project_path),
        "maya_mode": personality.current_mode().value,
        "context_session_id": unified_context.session_id
    })

# 3. Chat Pipeline
@app.route("/api/chat", methods=["POST"])
def handle_chat():
    data = request.get_json(silent=True) or {}
    message = data.get("message", "").strip()
    token = data.get("permission_token")
    if not message:
        return jsonify({"error": "No message provided"}), 400

    result = brain.process_request(message, permission_token=token)

    # If voice is enabled and conversational, synthesize speech asynchronously
    if settings.get("voice_enabled") and not result.get("requires_confirmation"):
        threading.Thread(
            target=voice.speak,
            args=(result.get("reply", ""),),
            daemon=True,
        ).start()

    return jsonify(result)

# 3b. Streaming Chat Pipeline
@app.route("/api/chat/stream", methods=["POST"])
def handle_chat_stream():
    """Stream ordinary chat as NDJSON; keep tool requests on the validated planner path."""
    data = request.get_json(silent=True) or {}
    message = data.get("message", "").strip()
    token = data.get("permission_token")
    if not message:
        return jsonify({"error": "No message provided"}), 400

    @stream_with_context
    def generate_events():
        final_result = None
        try:
            if brain.is_fast_conversation(message):
                for event in brain.stream_conversation(message):
                    if event.get("type") == "done":
                        final_result = event.get("result")
                    yield json.dumps(event, ensure_ascii=False) + "\n"
            else:
                final_result = brain.process_request(message, permission_token=token)
                yield json.dumps(
                    {"type": "done", "result": final_result},
                    ensure_ascii=False
                ) + "\n"

            if (
                settings.get("voice_enabled")
                and final_result
                and not final_result.get("requires_confirmation")
                and final_result.get("reply")
            ):
                threading.Thread(
                    target=voice.speak,
                    args=(final_result.get("reply", ""),),
                    daemon=True,
                ).start()
        except GeneratorExit:
            return
        except Exception as e:
            print(f"[MAYA Server] Streaming chat error: {e}")
            yield json.dumps(
                {"type": "error", "error": str(e)},
                ensure_ascii=False
            ) + "\n"

    response = Response(generate_events(), mimetype="application/x-ndjson")
    response.headers["Cache-Control"] = "no-cache, no-transform"
    response.headers["X-Accel-Buffering"] = "no"
    return response

# 4. Auth Bootstrap Endpoint
@app.route("/api/auth/token", methods=["GET"])
def get_auth_token():
    """Bootstrap session token for local UI clients with loopback isolation."""
    remote = request.remote_addr
    if remote not in ["127.0.0.1", "::1", "localhost"]:
        return jsonify({"error": "Forbidden: Non-loopback request"}), 403
    return jsonify({"token": AUTH_TOKEN})

# 5. Exact Plan Resumption
@app.route("/api/plans/<plan_id>/resume", methods=["POST"])
def resume_plan(plan_id: str):
    """Resumes exact suspended plan step upon permission authorization with single-use token."""
    data = request.get_json(silent=True) or {}
    confirmation_id = data.get("confirmation_id", "")
    permission_token = data.get("permission_token", "")
    if not confirmation_id or not permission_token:
        return jsonify({"error": "Missing confirmation_id or permission_token"}), 400

    result = planner.resume_plan(plan_id, confirmation_id, permission_token)
    return jsonify(result)

# 6. Plan Status Inspection
@app.route("/api/plans/<plan_id>", methods=["GET"])
def get_plan_status(plan_id: str):
    plan = planner.active_plans.get(plan_id)
    if not plan:
        return jsonify({"error": "Plan not found"}), 404
    return jsonify(plan.to_dict())

# 7. Action Confirmation & Token Issuance
@app.route("/api/action/confirm", methods=["POST"])
def confirm_action():
    data = request.get_json(silent=True) or {}
    conf_id = data.get("confirmation_id")
    approved = bool(data.get("approved", False))
    token = permissions.resolve_confirmation(conf_id, approved)
    if token:
        dispatch_event(PERMISSION_RESOLVED, {"confirmation_id": conf_id, "approved": True})
        return jsonify({"success": True, "permission_token": token})
    else:
        dispatch_event(PERMISSION_RESOLVED, {"confirmation_id": conf_id, "approved": False})
        return jsonify({"success": False, "message": "Confirmation rejected or expired"})

# 8. Task & Voice Cancellation
@app.route("/api/action/cancel", methods=["POST"])
def cancel_task():
    data = request.get_json(silent=True) or {}
    plan_id = data.get("plan_id")
    voice.stop_speaking()
    cancelled = planner.cancel_plan(plan_id) if plan_id else True
    dispatch_event(MAYA_STATE_CHANGED, {"state": "IDLE"})
    return jsonify({"success": True, "cancelled": cancelled})

# Voice Push-To-Talk
@app.route("/api/voice/ptt", methods=["POST"])
def voice_ptt():
    data = request.get_json(silent=True) or {}
    audio_b64 = data.get("audio_base64", "")
    if not audio_b64:
        return jsonify({"success": False, "error": "Missing audio_base64"}), 400
    try:
        wav_bytes = base64.b64decode(audio_b64)
        # Frontend sends a genuine 16-bit PCM WAV. Skip the 44-byte header
        # when calculating visual amplitude.
        pcm_preview = wav_bytes[44:2092] if wav_bytes[:4] == b"RIFF" else b""
        amp = calculate_pcm_rms(pcm_preview)
        dispatch_event(VOICE_LISTENING_AMPLITUDE, {"amplitude": amp})
        res = voice.process_ptt_audio(wav_bytes)
        return jsonify(res)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# MAYA Browser Bridge: authenticated extension command exchange
@app.route("/api/communication/next", methods=["GET"])
def communication_next():
    req_token = request.headers.get("X-Maya-Token", "").strip()
    if not req_token or not hmac.compare_digest(req_token, AUTH_TOKEN):
        return jsonify({"error": "Unauthorized"}), 401

    service = request.args.get("service", "").strip().lower()
    raw_tab_id = request.args.get("tab_id", "").strip()
    try:
        tab_id = int(raw_tab_id) if raw_tab_id else None
    except ValueError:
        tab_id = None
    command = communication_bridge.next_command(service, tab_id=tab_id)
    return jsonify({"command": command})


@app.route("/api/communication/attachment/<command_id>", methods=["GET"])
def communication_attachment(command_id: str):
    req_token = request.headers.get("X-Maya-Token", "").strip()
    if not req_token or not hmac.compare_digest(req_token, AUTH_TOKEN):
        return jsonify({"error": "Unauthorized"}), 401

    attachment = communication_bridge.get_attachment(command_id)
    if not attachment:
        return jsonify({"error": "No attachment is available for this active command."}), 404

    return send_file(
        attachment["path"],
        mimetype=attachment["mime_type"],
        as_attachment=True,
        download_name=attachment["name"],
        conditional=True,
    )


@app.route("/api/communication/result", methods=["POST"])
def communication_result():
    data = request.get_json(silent=True) or {}
    command_id = str(data.get("command_id", "")).strip()
    result = data.get("result")
    if not command_id or not isinstance(result, dict):
        return jsonify({"success": False, "error": "command_id and result are required"}), 400

    accepted = communication_bridge.complete(command_id, result)
    return jsonify({"success": accepted})


@app.route("/api/communication/contacts", methods=["POST"])
def communication_contacts_update():
    req_token = request.headers.get("X-Maya-Token", "").strip()
    if not req_token or not hmac.compare_digest(req_token, AUTH_TOKEN):
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json(silent=True) or {}
    service = str(data.get("service", "")).strip().lower()
    contacts = data.get("contacts", [])
    source = str(data.get("source", "browser")).strip() or "browser"
    if not isinstance(contacts, list):
        return jsonify({"success": False, "error": "contacts must be a list"}), 400

    result = communication_bridge.update_contacts(service, contacts, source=source)
    return jsonify(result), (200 if result.get("success") else 400)


@app.route("/api/communication/contacts", methods=["GET"])
def communication_contacts_list():
    req_token = request.headers.get("X-Maya-Token", "").strip()
    if not req_token or not hmac.compare_digest(req_token, AUTH_TOKEN):
        return jsonify({"error": "Unauthorized"}), 401

    service = request.args.get("service", "whatsapp").strip().lower()
    raw_limit = request.args.get("limit", "500")
    try:
        limit = max(1, min(int(raw_limit), 2000))
    except ValueError:
        limit = 500
    contacts = communication_bridge.list_contacts(service, limit=limit)
    return jsonify({
        "success": True,
        "service": service,
        "count": len(contacts),
        "contacts": contacts,
    })


@app.route("/api/communication/status", methods=["GET"])
def communication_status():
    req_token = request.headers.get("X-Maya-Token", "").strip()
    if not req_token or not hmac.compare_digest(req_token, AUTH_TOKEN):
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify(communication_bridge.status())


# Unified Context / Attachments
@app.route("/api/context", methods=["GET"])
def get_unified_context():
    req_token = request.headers.get("X-Maya-Token", "").strip()
    if not req_token or not hmac.compare_digest(req_token, AUTH_TOKEN):
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify(unified_context.session_summary())


@app.route("/api/browser/context", methods=["POST"])
def update_browser_context():
    data = request.get_json(silent=True) or {}
    communication_bridge.update_browser_context(data)
    return jsonify({"success": True})


@app.route("/api/browser/context", methods=["GET"])
def get_browser_context():
    req_token = request.headers.get("X-Maya-Token", "").strip()
    if not req_token or not hmac.compare_digest(req_token, AUTH_TOKEN):
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify(communication_bridge.get_browser_context())


@app.route("/api/attachments", methods=["POST"])
def upload_attachment():
    max_mb = int(settings.get("attachment_max_mb", 75))
    if request.content_length and request.content_length > max_mb * 1024 * 1024:
        return jsonify({
            "success": False,
            "error": f"Attachment exceeds the configured {max_mb} MB limit."
        }), 413

    upload = request.files.get("file")
    if upload is None or not upload.filename:
        return jsonify({"success": False, "error": "No attachment file provided."}), 400

    filename = secure_filename(upload.filename)
    if not filename:
        return jsonify({"success": False, "error": "Attachment filename is invalid."}), 400

    attachment_dir = unified_context.session_dir / "attachments"
    attachment_dir.mkdir(parents=True, exist_ok=True)
    target = attachment_dir / f"{int(time.time() * 1000)}_{filename}"
    upload.save(str(target))

    if target.stat().st_size > max_mb * 1024 * 1024:
        try:
            target.unlink()
        except Exception:
            pass
        return jsonify({
            "success": False,
            "error": f"Attachment exceeds the configured {max_mb} MB limit."
        }), 413

    analysis = attachment_intelligence.analyze(str(target))
    if not analysis.get("success"):
        return jsonify(analysis), 400

    # Keep the internal collision-safe path, but expose the original user-facing
    # filename in conversation/context.
    analysis["stored_name"] = target.name
    analysis["name"] = filename

    record = unified_context.register_attachment(analysis, label=filename)
    dispatch_event("context.attachment.added", {
        "id": record.get("id"),
        "name": record.get("name"),
        "type": record.get("type"),
        "summary": record.get("summary")
    })

    response = dict(record)
    context_text = str(response.get("context_text") or "")
    if len(context_text) > 6000:
        response["context_text"] = context_text[:6000] + "\n...[preview truncated]"
    return jsonify(response)


# 9. Action Ledger Activity
@app.route("/api/activity", methods=["GET"])
def get_activity():
    limit = int(request.args.get("limit", 15))
    actions = ledger.get_recent_actions(limit=limit)
    return jsonify({"actions": actions})

# 10. Action Rollback
@app.route("/api/action/rollback", methods=["POST"])
def rollback():
    data = request.get_json(silent=True) or {}
    aid = data.get("action_id")
    res = ledger.rollback_action(aid) if aid else ledger.rollback_last_action()
    dispatch_event(ACTION_ROLLED_BACK, res)
    return jsonify(res)

# 8. Diagnostics
@app.route("/api/diagnostics", methods=["GET"])
def run_diag():
    res = diagnostics.run_full_diagnostics()
    return jsonify(res)

# 9. Projects
@app.route("/api/projects", methods=["GET"])
def get_proj():
    details = developer.detect_project_details()
    mems = memory.get_all_memories()
    return jsonify({
        "active_project": details,
        "saved_projects": mems.get("projects", [])
    })

# 10. Memory
@app.route("/api/memory", methods=["GET"])
def get_mem():
    return jsonify({
        "memories": memory.get_all_memories(),
        "history": memory.get_conversation_history(limit=50)
    })

# 11. Skills
@app.route("/api/skills", methods=["GET"])
def get_sk():
    return jsonify({"skills": skills.list_skills()})

# 12. Settings API
@app.route("/api/settings", methods=["GET", "POST"])
def handle_settings():
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        for k, v in data.items():
            settings.set(k, v)
        if "permission_level" in data:
            permissions.set_max_level(PermissionLevel(int(data["permission_level"])))
        return jsonify({"success": True, "settings": settings.all()})
    return jsonify({"settings": settings.all()})

# 13. Hardware Profile
@app.route("/api/hardware", methods=["GET"])
def get_hw():
    return jsonify(get_hardware_profile())

def start_server(host="127.0.0.1", port=5000):
    print(f"Starting MAYA Core Server V2 on http://{host}:{port} ...")
    # Warm the local model before the first real conversation. The server
    # remains available while loading; /api/status reports readiness truthfully.
    threading.Thread(target=model_runtime.manager.warm_up, daemon=True).start()
    app.run(host=host, port=port, debug=False, use_reloader=False)

if __name__ == "__main__":
    start_server()
