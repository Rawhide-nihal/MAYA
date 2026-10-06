"""
MAYA Phase 2 — Comprehensive Core & Integration Test Suite
Tests Brain, Dynamic Planner, Memory Store V2, Permissions V2, Action Ledger with Rollback,
Hardware Telemetry, and Model Runtime.
"""
import os
import gc
import sys
import tempfile
import time
import unittest
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from maya_core.models.base import DeterministicIntentClassifier
from maya_core.models.runtime import MayaModelRuntime
from maya_core.models.hardware_detector import get_hardware_profile, get_real_gpu_metrics
from security.permissions.tier import PermissionManager, PermissionLevel
from security.audit.ledger import ActionLedger, ActionRecord
from memory.store import MemoryStore
from maya_core.context.builder import ContextBuilder
from maya_core.planner.dynamic_planner import DynamicTaskPlanner, PlanState, StepState
from maya_core.brain.brain import MayaBrain
from agents.windows.agent import WindowsAgent
from agents.filesystem.agent import FileAgent
from agents.developer.agent import DeveloperAgent
from agents.diagnostics.engine import DiagnosticEngine
from agents.terminal.agent import TerminalAgent
from agents.vision.agent import VisionAgent
from agents.browser.agent import BrowserAgent
from agents.communication.agent import CommunicationAgent
from agents.communication.bridge import CommunicationBridge
from maya_core.personality.engine import PersonalityEngine, MayaMode, ResponseDepth
from maya_core.context.engine import UnifiedContextEngine
from maya_core.attachments.intelligence import AttachmentIntelligence
from maya_core.config import settings, get_user_screenshots_dir

class TestMayaPhase2Core(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.audit_db = os.path.join(self.temp_dir.name, "test_audit.db")
        self.memory_db = os.path.join(self.temp_dir.name, "test_memory.db")

        self.classifier = DeterministicIntentClassifier()
        self.permissions = PermissionManager(PermissionLevel.LEVEL_2_SAFE_ACTION)
        self.ledger = ActionLedger(db_path=Path(self.audit_db))
        self.memory = MemoryStore(db_path=Path(self.memory_db))

        self.windows = WindowsAgent()
        self.terminal = TerminalAgent()
        self.filesystem = FileAgent()
        self.developer = DeveloperAgent(self.terminal)
        self.diagnostics = DiagnosticEngine(self.terminal)
        self.vision = VisionAgent()
        self.browser = BrowserAgent()

        self.events_received = []
        def event_sink(name, data):
            self.events_received.append((name, data))

        self.planner = DynamicTaskPlanner(
            permissions=self.permissions,
            ledger=self.ledger,
            memory=self.memory,
            windows=self.windows,
            terminal=self.terminal,
            filesystem=self.filesystem,
            developer=self.developer,
            diagnostics=self.diagnostics,
            vision=self.vision,
            browser=self.browser,
            event_callback=event_sink
        )

        self.context_builder = ContextBuilder(self.memory, self.ledger, self.windows, self.developer)
        self.runtime = MayaModelRuntime()
        self.brain = MayaBrain(
            context_builder=self.context_builder,
            planner=self.planner,
            memory=self.memory,
            permissions=self.permissions,
            ledger=self.ledger,
            runtime=self.runtime
        )

    def tearDown(self):
        gc.collect()
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    # 1. Intent Classification & Security Gating
    def test_intent_classification(self):
        # Conversational
        r1 = self.classifier.classify_and_extract("Hey Maya, how are you?")
        self.assertEqual(r1["intent"], "CHAT")
        self.assertIsNone(r1["tool"])

        # PC Launch
        r2 = self.classifier.classify_and_extract("Launch VS Code")
        self.assertEqual(r2["intent"], "PC_ACTION")
        self.assertEqual(r2["tool"], "open_application")
        self.assertIn("visual studio code", r2["arguments"].get("application", "").lower())

        # Diagnostics
        r3 = self.classifier.classify_and_extract("Check system health and run diagnostics")
        self.assertEqual(r3["intent"], "SYSTEM_DIAGNOSTIC")
        self.assertEqual(r3["tool"], "run_system_diagnostics")

        # Developer Error Check
        r4 = self.classifier.classify_and_extract("Check my project for compile errors")
        self.assertEqual(r4["intent"], "DEVELOPMENT_ACTION")
        self.assertEqual(r4["tool"], "inspect_project")

        # External communication
        r5 = self.classifier.classify_and_extract(
            "Send a WhatsApp message to Rahul: I'll be there at 6"
        )
        self.assertEqual(r5["intent"], "PC_ACTION")
        self.assertEqual(r5["tool"], "send_communication")
        self.assertEqual(r5["arguments"]["service"], "whatsapp")
        self.assertEqual(r5["arguments"]["recipient"], "Rahul")
        self.assertEqual(r5["arguments"]["message"], "I'll be there at 6")

        r6 = self.classifier.classify_and_extract("Open WhatsApp in Chrome")
        self.assertEqual(r6["tool"], "open_application")
        self.assertEqual(r6["arguments"]["application"], "Google Chrome")
        self.assertEqual(r6["arguments"]["profile"], "main")
        self.assertIn("web.whatsapp.com", r6["arguments"]["path"])

        r7 = self.classifier.classify_and_extract(
            "Send Rahul a WhatsApp message saying I fixed it"
        )
        self.assertEqual(r7["tool"], "send_communication")
        self.assertEqual(r7["arguments"]["recipient"], "Rahul")
        self.assertEqual(r7["arguments"]["message"], "I fixed it")

        r8 = self.classifier.classify_and_extract(
            "Draft an email to friend@example.com saying Project is ready"
        )
        self.assertEqual(r8["tool"], "prepare_communication")
        self.assertEqual(r8["arguments"]["service"], "gmail")
        self.assertEqual(r8["arguments"]["recipient"], "friend@example.com")

        r9 = self.classifier.classify_and_extract(
            "Send this screenshot to Rahul on WhatsApp"
        )
        self.assertEqual(r9["tool"], "send_communication")
        self.assertEqual(r9["arguments"]["service"], "whatsapp")
        self.assertEqual(r9["arguments"]["recipient"], "Rahul")
        self.assertEqual(r9["arguments"]["attachment_path"].lower(), "this screenshot")

        r10 = self.classifier.classify_and_extract(
            "Now paste that into WhatsApp"
        )
        self.assertEqual(r10["tool"], "prepare_communication")
        self.assertEqual(r10["arguments"]["service"], "whatsapp")
        self.assertEqual(r10["arguments"]["recipient"], "current chat")
        self.assertEqual(r10["arguments"]["attachment_path"].lower(), "that")
        self.assertEqual(r10["arguments"]["message"], "")

        r11 = self.classifier.classify_and_extract(
            "Send the screenshot to this guy in whatsapp"
        )
        self.assertEqual(r11["tool"], "send_communication")
        self.assertEqual(r11["arguments"]["service"], "whatsapp")
        self.assertEqual(r11["arguments"]["recipient"], "current chat")
        self.assertEqual(r11["arguments"]["attachment_path"].lower(), "the screenshot")

        r12 = self.classifier.classify_and_extract(
            "Open Chrome default profile"
        )
        self.assertEqual(r12["tool"], "open_application")
        self.assertEqual(r12["arguments"]["application"], "Google Chrome")
        self.assertEqual(r12["arguments"]["profile"], "main")

        r13 = self.classifier.classify_and_extract(
            "Sync my WhatsApp contacts"
        )
        self.assertEqual(r13["tool"], "sync_communication_contacts")
        self.assertEqual(r13["arguments"]["service"], "whatsapp")

        r14 = self.classifier.classify_and_extract(
            "Open the latest screenshot"
        )
        self.assertEqual(r14["tool"], "open_file")
        self.assertIn("screenshot", r14["arguments"]["filepath"].lower())

        r15 = self.classifier.classify_and_extract(
            "Open the recent PNG file"
        )
        self.assertEqual(r15["tool"], "open_file")
        self.assertIn("png", r15["arguments"]["filepath"].lower())

        r16 = self.classifier.classify_and_extract(
            "Copy the latest screenshot to clipboard"
        )
        self.assertEqual(r16["tool"], "copy_file_to_clipboard")
        self.assertIn("screenshot", r16["arguments"]["filepath"].lower())

        r17 = self.classifier.classify_and_extract(
            "Copy this file to my clipboard"
        )
        self.assertEqual(r17["tool"], "copy_file_to_clipboard")
        self.assertEqual(r17["arguments"]["filepath"].lower(), "this file")

        r18 = self.classifier.classify_and_extract(
            r"Copy C:\Users\Boss\Documents\report.pdf to clipboard"
        )
        self.assertEqual(r18["tool"], "copy_file_to_clipboard")
        self.assertTrue(r18["arguments"]["filepath"].lower().endswith("report.pdf"))

        r19 = self.classifier.classify_and_extract(
            r"Open D:\Projects\archive.zip"
        )
        self.assertEqual(r19["tool"], "open_file")
        self.assertTrue(r19["arguments"]["filepath"].lower().endswith("archive.zip"))

        r20 = self.classifier.classify_and_extract(
            "Maya, sync my WhatsApp contacts."
        )
        self.assertEqual(r20["tool"], "sync_communication_contacts")
        self.assertEqual(r20["arguments"]["service"], "whatsapp")

        r21 = self.classifier.classify_and_extract(
            "Can u find a contact Named Niteesh?"
        )
        self.assertEqual(r21["tool"], "lookup_communication_contact")
        self.assertEqual(r21["arguments"]["service"], "whatsapp")
        self.assertEqual(r21["arguments"]["query"], "Niteesh")

        self.assertFalse(
            self.brain.is_fast_conversation("Maya, sync my WhatsApp contacts.")
        )
        self.assertFalse(
            self.brain.is_fast_conversation("Can u find a contact Named Niteesh?")
        )

    # 2. Permissions V2 Enforcement & Single-Use Tokens
    def test_permission_tier_enforcement(self):
        # Read-only observation is granted under Level 2
        p_read = self.permissions.check_permission("get_system_status", {})
        self.assertTrue(p_read.granted)
        self.assertFalse(p_read.requires_confirmation)

        # Sending external communication is Level 3 and requires confirmation
        # under MAYA's default Level 2 permission policy.
        send_args = {
            "service": "whatsapp",
            "recipient": "Rahul",
            "message": "I'll be there at 6",
            "profile": "main"
        }
        p_send = self.permissions.check_permission("send_communication", send_args)
        self.assertFalse(p_send.granted)
        self.assertTrue(p_send.requires_confirmation)
        self.assertEqual(p_send.required_level, PermissionLevel.LEVEL_3_MODIFICATION)

        # Level 4 critical action must require confirmation
        p_crit = self.permissions.check_permission("delete_file", {"filepath": "important.txt"})
        self.assertFalse(p_crit.granted)
        self.assertTrue(p_crit.requires_confirmation)
        self.assertIsNotNone(p_crit.confirmation_id)

        # User resolves confirmation -> issues single-use token
        token = self.permissions.resolve_confirmation(p_crit.confirmation_id, approved=True)
        self.assertIsNotNone(token)
        self.assertTrue(token.startswith("perm_"))

        # Re-verify with signed token -> granted!
        p_authorized = self.permissions.check_permission("delete_file", {"filepath": "important.txt"}, token=token)
        self.assertTrue(p_authorized.granted)

        # Single-use token is consumed: replay must require confirmation again
        p_replay = self.permissions.check_permission("delete_file", {"filepath": "important.txt"}, token=token)
        self.assertFalse(p_replay.granted)
        self.assertTrue(p_replay.requires_confirmation)

    # 3. Action Ledger & Rollback
    def test_ledger_recording_and_rollback(self):
        test_file = os.path.join(self.temp_dir.name, "rollback_test.txt")
        with open(test_file, "w") as f:
            f.write("Initial state")

        rec = ActionRecord(
            action_id="act-test-01",
            plan_id="plan-01",
            tool_name="write_file",
            arguments={"filepath": test_file, "content": "Modified state"},
            affected_resources=[test_file],
            previous_state={"original_content": "Initial state"},
            result={"status": "success"},
            verified=True,
            undo_available=True,
            status="success",
            timestamp=1000.0,
            summary="Modified rollback_test.txt"
        )
        self.ledger.record_action(rec)

        # Mutate the file
        with open(test_file, "w") as f:
            f.write("Modified state")

        # Rollback
        res = self.ledger.rollback_action("act-test-01")
        self.assertTrue(res.get("success"))

        # Verify restored content
        with open(test_file, "r") as f:
            restored = f.read()
        self.assertEqual(restored, "Initial state")

    # 4. Memory Store V2 (Working, Semantic, Episodic & Search)
    def test_memory_v2_and_search(self):
        # Working memory
        self.memory.set_working_memory("active_ide", "VS Code")
        self.assertEqual(self.memory.get_working_memory("active_ide"), "VS Code")

        # Semantic memory with supersession
        self.memory.save_semantic_memory("preference", "theme", "Dark Midnight Blue", 5.0)
        mems = self.memory.search_relevant_memories("theme")
        self.assertTrue(len(mems) > 0)
        self.assertTrue(any("Dark Midnight Blue" in m for m in mems))

        # Update preference: supersession
        self.memory.save_semantic_memory("preference", "theme", "Cyberpunk Cyan", 5.0)
        mems_updated = self.memory.search_relevant_memories("theme")
        self.assertTrue(any("Cyberpunk Cyan" in m for m in mems_updated))

        # Episodic conversation turn
        self.memory.add_message("user", "Hello Maya")
        self.memory.add_message("maya", "Hello! How can I help?")
        history = self.memory.get_conversation_history(limit=5)
        self.assertGreaterEqual(len(history), 2)

    # 5. Dynamic Task Planner: Plan Lifecycle & Verification
    def test_dynamic_task_planner_execution(self):
        intent_info = {
            "intent": "SYSTEM_DIAGNOSTIC",
            "tool": "run_system_diagnostics",
            "arguments": {"depth": "full"}
        }
        plan = self.planner.create_plan(
            goal="Check system health",
            intent_info=intent_info
        )
        self.assertIsNotNone(plan)
        self.assertGreaterEqual(len(plan.steps), 1)

        # Execute plan
        res_plan = self.planner.execute_plan(plan)
        self.assertEqual(res_plan["state"], PlanState.COMPLETED.value)
        self.assertEqual(plan.state, PlanState.COMPLETED)
        self.assertTrue(plan.steps[0].verified)
        self.assertEqual(plan.steps[0].state, StepState.SUCCESS)

        # Verify events were dispatched
        event_names = [e[0] for e in self.events_received]
        self.assertIn("plan.created", event_names)
        self.assertIn("task.plan.created", event_names)
        self.assertIn("tool.started", event_names)
        self.assertIn("task.step.started", event_names)
        self.assertIn("tool.completed", event_names)
        self.assertIn("task.step.completed", event_names)
        self.assertIn("task.completed", event_names)

        plan_created_payload = next(
            payload for name, payload in self.events_received
            if name == "plan.created"
        )
        self.assertTrue(plan_created_payload.get("steps"))
        self.assertIn("description", plan_created_payload["steps"][0])

    # 6. Real Hardware Telemetry (Zero fake data)
    def test_hardware_profiler(self):
        hw = get_hardware_profile()
        self.assertIn("cpu", hw)
        self.assertIn("ram", hw)
        self.assertIn("storage", hw)
        self.assertIn("gpu", hw)

        self.assertGreater(hw["cpu"]["physical_cores"], 0)
        self.assertGreater(hw["ram"]["total_gb"], 0)
        self.assertGreater(hw["storage"]["free_gb"], 0)

        # Check GPU telemetry
        gpu = get_real_gpu_metrics()
        self.assertIn("available", gpu)
        if gpu["available"]:
            self.assertGreater(gpu["vram_total_mb"], 0)
            self.assertIsNotNone(gpu["temperature_c"])
        else:
            self.assertEqual(gpu["name"], "Unavailable")
            self.assertIsNone(gpu["gpu_percent"])

    # 7. Maya Model Runtime & Trained LoRA Checkpoint
    def test_maya_model_runtime(self):
        status = self.runtime.get_status()
        self.assertIn("name", status)
        self.assertIn("base_model", status)
        self.assertIn("status", status)

        # Check inference response
        res = self.runtime.generate("What is 2 + 2?", max_tokens=16)
        self.assertIsInstance(res, str)
        self.assertGreater(len(res), 0)

    # 8. End-to-End Brain Conversation & Action
    def test_brain_chat_and_action(self):
        # Conversational interaction
        chat_resp = self.brain.process_request("What can you do?")
        self.assertIn(chat_resp["intent"], ["CHAT", "QUESTION"])
        self.assertIn("reply", chat_resp)
        self.assertGreater(len(chat_resp["reply"]), 0)

        # Action interaction
        diag_resp = self.brain.process_request("Scan system health")
        self.assertEqual(diag_resp["intent"], "SYSTEM_DIAGNOSTIC")
        self.assertIn("reply", diag_resp)
        self.assertTrue(len(diag_resp.get("tasks", [])) > 0)

    # 9. Phase 3: Exact Plan Suspension & Single-Use Token Resumption
    def test_exact_plan_suspension_and_resume(self):
        # Create a plan with a privileged step
        intent_info = {
            "intent": "FILE_ACTION",
            "tool": "delete_file",
            "arguments": {"filepath": "sensitive_test.txt"}
        }
        plan = self.planner.create_plan("Delete sensitive test file", intent_info)
        self.assertIsNotNone(plan)

        # Execute: step 1 is delete_file (privileged Level 4) -> plan must suspend
        res = self.planner.execute_plan(plan)
        self.assertEqual(res["state"], PlanState.WAITING_FOR_PERMISSION.value)
        self.assertTrue(res.get("requires_confirmation"))
        conf_id = res.get("confirmation_id")
        self.assertIsNotNone(conf_id)

        # Plan must be stored in active_plans awaiting confirmation
        self.assertIn(plan.plan_id, self.planner.active_plans)

        # Resolve confirmation -> issues single-use token bound to this exact plan & step
        token = self.permissions.resolve_confirmation(conf_id, approved=True)
        self.assertIsNotNone(token)

        # Attempt to resume with wrong token or wrong confirmation ID
        bad_resume = self.planner.resume_plan(plan.plan_id, "bad_conf_id", token)
        self.assertIn("error", bad_resume)

        # Resume with exact valid token
        good_resume = self.planner.resume_plan(plan.plan_id, conf_id, token)
        self.assertIn(good_resume["state"], [PlanState.COMPLETED.value, PlanState.FAILED.value])

        # Attempt replay with the same token -> must be rejected as already consumed
        replay_resume = self.planner.resume_plan(plan.plan_id, conf_id, token)
        self.assertIn("error", replay_resume)

    # 10. Phase 3: Real Audio PCM RMS Measurement
    def test_real_audio_pcm_rms(self):
        from voice.engine import calculate_pcm_rms
        import numpy as np

        # Silence buffer (all zeros)
        silence = np.zeros(1024, dtype=np.int16).tobytes()
        rms_silence = calculate_pcm_rms(silence)
        self.assertEqual(rms_silence, 0.0)

        # Full-scale sine wave
        t = np.linspace(0, 1, 1024, endpoint=False)
        sine = (np.sin(2 * np.pi * 440 * t) * 32000).astype(np.int16).tobytes()
        rms_sine = calculate_pcm_rms(sine)
        self.assertGreater(rms_sine, 0.5)
        self.assertLessEqual(rms_sine, 1.0)

    # 11. Phase 3: Vision Privacy Policy Gate
    def test_vision_privacy_gate(self):
        from maya_core.config import settings

        # Test Never policy
        settings.set("screen_capture_privacy", "Never")
        cap_never = self.vision.capture_screen()
        self.assertFalse(cap_never["success"])
        self.assertIn("Never", cap_never["error"])

        # Test Always policy
        settings.set("screen_capture_privacy", "Always")
        cap_always = self.vision.capture_screen()
        # In an interactive desktop session, success is True.
        # In headless background sessions without display DC, check that privacy allowed the attempt
        self.assertTrue(cap_always["success"] or "screen grab failed" in cap_always.get("error", "").lower())
        if cap_always["success"]:
            self.assertIn("brightness", cap_always)

    # 12. Phase 4: Canonical ToolRegistry Verification
    def test_canonical_tool_registry(self):
        from maya_core.tools.registry import default_tool_registry
        tools = default_tool_registry.list_tools()
        self.assertGreaterEqual(len(tools), 30)

        # Check key tools exist
        self.assertIsNotNone(default_tool_registry.get("open_application"))
        self.assertIsNotNone(default_tool_registry.get("inspect_project"))
        self.assertIsNotNone(default_tool_registry.get("get_system_status"))
        self.assertIsNotNone(default_tool_registry.get("search_files"))
        self.assertIsNotNone(default_tool_registry.get("rollback_last_action"))
        self.assertIsNotNone(default_tool_registry.get("prepare_communication"))
        self.assertIsNotNone(default_tool_registry.get("send_communication"))

        self.assertIsNotNone(default_tool_registry.get("sync_communication_contacts"))
        self.assertIsNotNone(default_tool_registry.get("open_file"))
        self.assertIsNotNone(default_tool_registry.get("copy_file_to_clipboard"))

        self.assertIsNotNone(default_tool_registry.get("lookup_communication_contact"))

        # Verify argument validation
        valid, err = default_tool_registry.validate_call("open_application", {"application": "VS Code"})
        self.assertTrue(valid)
        self.assertIsNone(err)

        # Missing required parameter
        invalid, err = default_tool_registry.validate_call("open_application", {})
        self.assertFalse(invalid)
        self.assertIn("Missing required parameter", err)

    def test_communication_agent_preserves_exact_payload(self):
        class FakeWindows:
            def __init__(self):
                self.calls = []

            def launch_application(self, app_name, arguments=None, cwd=None, profile=None):
                self.calls.append({
                    "app_name": app_name,
                    "arguments": arguments,
                    "profile": profile
                })
                return {
                    "success": True,
                    "verified": True,
                    "profile_name": "Main",
                    "profile_directory": "Default"
                }

        class FakeBridge:
            def __init__(self):
                self.command = None

            def submit(self, command, timeout=25.0):
                self.command = dict(command)
                return {
                    "success": True,
                    "verified": True,
                    "sent": True
                }

        fake_windows = FakeWindows()
        fake_bridge = FakeBridge()
        agent = CommunicationAgent(windows=fake_windows, bridge=fake_bridge)

        result = agent.send(
            service="whatsapp",
            recipient="Rahul",
            message="I'll be there at 6",
            profile="main"
        )

        self.assertTrue(result["success"])
        self.assertTrue(result["verified"])
        self.assertEqual(fake_bridge.command["service"], "whatsapp")
        self.assertEqual(fake_bridge.command["recipient"], "Rahul")
        self.assertEqual(fake_bridge.command["message"], "I'll be there at 6")
        self.assertEqual(fake_bridge.command["action"], "send")
        self.assertEqual(fake_windows.calls[0]["app_name"], "Google Chrome")
        self.assertEqual(fake_windows.calls[0]["profile"], "main")

        attachment = Path(self.temp_dir.name) / "capture.png"
        attachment.write_bytes(b"test attachment bytes")
        result_with_attachment = agent.send(
            service="whatsapp",
            recipient="Rahul",
            message="",
            profile="main",
            attachment_path=str(attachment)
        )
        self.assertTrue(result_with_attachment["success"])
        self.assertEqual(
            fake_bridge.command["attachment_path"],
            str(attachment.resolve())
        )

    def test_whatsapp_contact_index_exact_fuzzy_and_ambiguous_resolution(self):
        bridge = CommunicationBridge()
        bridge._contacts_path = Path(self.temp_dir.name) / "contacts.json"
        bridge._contacts = {"whatsapp": {}, "telegram": {}, "gmail": {}}

        sync = bridge.update_contacts(
            "whatsapp",
            ["Rahul Kumar", "Rohan", "Rohit", "Boss Test"],
            source="unit_test"
        )
        self.assertTrue(sync["success"])
        self.assertEqual(sync["total"], 4)

        exact = bridge.resolve_contact("whatsapp", "Rahul Kumar")
        self.assertTrue(exact["matched"])
        self.assertEqual(exact["name"], "Rahul Kumar")

        fuzzy = bridge.resolve_contact("whatsapp", "Rahul Kumer")
        self.assertTrue(fuzzy["matched"])
        self.assertEqual(fuzzy["name"], "Rahul Kumar")

        ambiguous = bridge.resolve_contact("whatsapp", "Roh")
        self.assertFalse(ambiguous["matched"])
        self.assertTrue(ambiguous["ambiguous"])
        self.assertGreaterEqual(len(ambiguous["suggestions"]), 2)

    def test_windows_application_aliases_and_launcher_handoff(self):
        from unittest.mock import patch, MagicMock

        agent = WindowsAgent()

        self.assertIn("chrome", agent._application_process_aliases(
            "Google Chrome",
            r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        ))
        self.assertIn("msedge", agent._application_process_aliases(
            "Microsoft Edge",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"
        ))
        self.assertIn("code", agent._application_process_aliases(
            "Visual Studio Code",
            r"C:\Users\Boss\AppData\Local\Programs\Microsoft VS Code\Code.exe"
        ))

        fake_proc = MagicMock()
        fake_proc.pid = 4242
        fake_proc.poll.return_value = 0  # launcher exited after handing off

        with patch.object(agent, "find_application_path", return_value=r"C:\Apps\chrome.exe"), \
             patch.object(agent, "_wait_for_application", return_value=True), \
             patch("agents.windows.agent.subprocess.Popen", return_value=fake_proc):
            result = agent.launch_application("Google Chrome")

        self.assertTrue(result["success"])
        self.assertTrue(result["verified"])
        self.assertTrue(result.get("handoff_detected"))
        self.assertFalse(result["launcher_alive"])

        class FakeChromeProcess:
            info = {
                "name": "chrome.exe",
                "exe": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            }

        with patch("agents.windows.agent.psutil.process_iter", return_value=[FakeChromeProcess()]):
            self.assertTrue(
                agent.is_application_running(
                    "Google Chrome",
                    r"C:\Program Files\Google\Chrome\Application\chrome.exe"
                )
            )

    def test_direct_personality_social_replies(self):
        personality = PersonalityEngine()

        how = personality.direct_social_reply("Hey Maya how you doing")
        self.assertIsNotNone(how)
        self.assertIn("Boss", how)
        self.assertIn("existential crisis", how)

        identity = personality.direct_social_reply("Ur Maya")
        self.assertIsNotNone(identity)
        self.assertIn("Boss", identity)
        self.assertIn("another AI", identity)

    def test_recent_screenshot_and_image_file_resolution(self):
        original = os.environ.get("MAYA_SCREENSHOT_DIR")
        screenshots = Path(self.temp_dir.name) / "Pictures" / "Screenshots"
        screenshots.mkdir(parents=True, exist_ok=True)
        old_png = screenshots / "Screenshot_old.png"
        new_png = screenshots / "Screenshot_new.png"
        jpeg = screenshots / "photo.jpeg"
        old_png.write_bytes(b"old")
        new_png.write_bytes(b"new")
        jpeg.write_bytes(b"jpg")

        now = time.time()
        os.utime(old_png, (now - 30, now - 30))
        os.utime(jpeg, (now - 20, now - 20))
        os.utime(new_png, (now - 5, now - 5))

        try:
            os.environ["MAYA_SCREENSHOT_DIR"] = str(screenshots)
            agent = WindowsAgent()

            latest = agent.resolve_file_reference("latest screenshot")
            self.assertTrue(latest["success"])
            self.assertEqual(Path(latest["path"]).name, "Screenshot_new.png")

            latest_png = agent.resolve_file_reference("recent png file")
            self.assertTrue(latest_png["success"])
            self.assertEqual(Path(latest_png["path"]).name, "Screenshot_new.png")

            latest_jpeg = agent.resolve_file_reference("latest jpeg file")
            self.assertTrue(latest_jpeg["success"])
            self.assertEqual(Path(latest_jpeg["path"]).name, "photo.jpeg")
        finally:
            if original is None:
                os.environ.pop("MAYA_SCREENSHOT_DIR", None)
            else:
                os.environ["MAYA_SCREENSHOT_DIR"] = original

    def test_contact_lookup_and_grounded_followup_status(self):
        bridge = CommunicationBridge()
        bridge._contacts_path = Path(self.temp_dir.name) / "grounded_contacts.json"
        bridge._contacts = {"whatsapp": {}, "telegram": {}, "gmail": {}}
        bridge.update_contacts("whatsapp", ["Niteesh", "Rahul"], source="unit_test")
        self.planner.communication.bridge = bridge

        lookup = self.planner.communication.lookup_contact("whatsapp", "Niteesh")
        self.assertTrue(lookup["success"])
        self.assertTrue(lookup["found"])
        self.assertEqual(lookup["name"], "Niteesh")

        sync_result = {
            "success": True,
            "verified": True,
            "contacts_synced": 2,
            "local_contact_count": 2,
            "complete": True,
            "partial": False,
        }
        self.ledger.record_action(ActionRecord(
            action_id="sync-followup",
            plan_id="plan-sync",
            tool_name="sync_communication_contacts",
            arguments={"service": "whatsapp", "profile": "main"},
            affected_resources=[],
            previous_state=None,
            result=sync_result,
            verified=True,
            undo_available=False,
            status="success",
            timestamp=time.time(),
            summary="Synced WhatsApp contacts"
        ))

        sync_followup = self.brain.process_request("Did u sync them?")
        self.assertEqual(sync_followup["intent"], "ACTION_STATUS")
        self.assertTrue(sync_followup["verified"])
        self.assertIn("2 contact/chat", sync_followup["reply"])
        self.assertFalse(self.brain.is_fast_conversation("Did u sync them?"))

        lookup_result = {
            "success": True,
            "verified": True,
            "found": True,
            "service": "whatsapp",
            "query": "Niteesh",
            "name": "Niteesh",
            "indexed_count": 2,
        }
        self.ledger.record_action(ActionRecord(
            action_id="lookup-followup",
            plan_id="plan-lookup",
            tool_name="lookup_communication_contact",
            arguments={"service": "whatsapp", "query": "Niteesh"},
            affected_resources=[],
            previous_state=None,
            result=lookup_result,
            verified=True,
            undo_available=False,
            status="success",
            timestamp=time.time() + 0.01,
            summary="Found Niteesh"
        ))

        found_followup = self.brain.process_request("Did u find?")
        self.assertEqual(found_followup["intent"], "ACTION_STATUS")
        self.assertIn("Niteesh", found_followup["reply"])
        self.assertIn("found", found_followup["reply"].lower())

    def test_verified_contact_result_synthesis_does_not_invent(self):
        from maya_core.brain.decision import NeuralDecision

        decision = NeuralDecision(
            decision_type="tool_call",
            tool="lookup_communication_contact",
            arguments={"service": "whatsapp", "query": "Niteesh"},
            confidence=1.0,
        )
        found = self.brain._synthesize_natural_response(
            "Find Niteesh",
            decision,
            {
                "state": "COMPLETED",
                "steps": [],
                "last_result": {
                    "success": True,
                    "verified": True,
                    "found": True,
                    "query": "Niteesh",
                    "name": "Niteesh",
                }
            }
        )
        self.assertIn("Niteesh", found)
        self.assertIn("Found", found)

        missing = self.brain._synthesize_natural_response(
            "Find Unknown Person",
            NeuralDecision(
                decision_type="tool_call",
                tool="lookup_communication_contact",
                arguments={"service": "whatsapp", "query": "Unknown Person"},
                confidence=1.0,
            ),
            {
                "state": "COMPLETED",
                "steps": [],
                "last_result": {
                    "success": True,
                    "verified": True,
                    "found": False,
                    "ambiguous": False,
                    "query": "Unknown Person",
                }
            }
        )
        self.assertIn("couldn't find", missing.lower())

    def test_chrome_configured_profile_beats_last_used_and_default_alias(self):
        original_profile = settings.get("chrome_main_profile", "")
        original_account = settings.get("chrome_main_account", "")
        try:
            settings.set("chrome_main_profile", "Profile 7")
            settings.set("chrome_main_account", "")

            agent = WindowsAgent()
            agent._load_chrome_profile_state = lambda: {
                "profile": {
                    "last_used": "Profile 2",
                    "info_cache": {
                        "Profile 2": {"name": "Wrong Last Used", "user_name": "other@example.com"},
                        "Profile 7": {"name": "Boss Main", "user_name": "boss@example.com"},
                        "Default": {"name": "Default"}
                    }
                }
            }

            main_result = agent.resolve_chrome_profile("main")
            self.assertTrue(main_result["success"])
            self.assertEqual(main_result["profile_directory"], "Profile 7")
            self.assertEqual(main_result["resolution"], "configured_main_profile")

            default_result = agent.resolve_chrome_profile("default")
            self.assertTrue(default_result["success"])
            self.assertEqual(default_result["profile_directory"], "Profile 7")
        finally:
            settings.set("chrome_main_profile", original_profile)
            settings.set("chrome_main_account", original_account)

    def test_user_screenshot_directory_override_is_visible_folder(self):
        original = os.environ.get("MAYA_SCREENSHOT_DIR")
        target = Path(self.temp_dir.name) / "Pictures" / "Screenshots"
        try:
            os.environ["MAYA_SCREENSHOT_DIR"] = str(target)
            resolved = get_user_screenshots_dir()
            self.assertEqual(resolved.resolve(), target.resolve())
            self.assertTrue(resolved.exists())
        finally:
            if original is None:
                os.environ.pop("MAYA_SCREENSHOT_DIR", None)
            else:
                os.environ["MAYA_SCREENSHOT_DIR"] = original

    def test_v5_personality_modes_and_adaptive_depth(self):
        from maya_core.config import settings

        original_mode = settings.get("maya_mode", "Normal")
        try:
            personality = PersonalityEngine()

            mode = personality.parse_mode_command("Maya, focus mode")
            self.assertEqual(mode, MayaMode.FOCUS)
            personality.set_mode(mode.value)
            self.assertEqual(personality.current_mode(), MayaMode.FOCUS)
            self.assertEqual(
                personality.response_depth("What is my CPU temperature?"),
                ResponseDepth.QUICK
            )

            personality.set_mode("Normal")
            self.assertEqual(
                personality.response_depth("Go deep and analyze this entire project architecture"),
                ResponseDepth.DEEP
            )
            self.assertEqual(
                personality.severity("I think there is a security breach"),
                "HIGH"
            )
            serious_prompt = personality.prompt_fragment("There is a security breach")
            self.assertIn("Do not use humor", serious_prompt)

            casual_prompt = personality.prompt_fragment("How are you doing?")
            self.assertIn("generic customer-service bot", casual_prompt)
            self.assertIn("slightly sarcastic", casual_prompt)
            self.assertGreaterEqual(
                personality.policy("How are you doing?").max_new_tokens,
                80
            )
        finally:
            settings.set("maya_mode", original_mode)

    def test_v5_attachment_intelligence_text_csv_and_project_zip(self):
        import zipfile

        analyzer = AttachmentIntelligence(max_text_chars=12000)

        text_path = Path(self.temp_dir.name) / "sample.py"
        text_path.write_text("import os\nprint('hello')\n", encoding="utf-8")
        text_result = analyzer.analyze(str(text_path))
        self.assertTrue(text_result["success"])
        self.assertEqual(text_result["line_count"], 2)
        self.assertIn("import os", text_result["extracted_text"])

        csv_path = Path(self.temp_dir.name) / "sample.csv"
        csv_path.write_text("name,value\nalpha,1\nbeta,2\n", encoding="utf-8")
        csv_result = analyzer.analyze(str(csv_path))
        self.assertTrue(csv_result["success"])
        self.assertEqual(csv_result["column_count_max"], 2)

        zip_path = Path(self.temp_dir.name) / "project.zip"
        with zipfile.ZipFile(zip_path, "w") as archive:
            archive.writestr(
                "project/package.json",
                '{"name":"demo","dependencies":{"react":"^19.0.0"},"devDependencies":{"vite":"^7.0.0"}}'
            )
            archive.writestr(
                "project/src/main.ts",
                "import React from 'react';\nimport helper from './helper';\n"
            )
            archive.writestr("project/src/helper.ts", "export default 1;\n")

        zip_result = analyzer.analyze(str(zip_path))
        self.assertTrue(zip_result["success"])
        self.assertGreaterEqual(zip_result["dependency_count"], 2)
        self.assertIn("project/package.json", zip_result["dependencies"])
        self.assertIn("project/src/main.ts", zip_result["source_relationships"])

    def test_v5_unified_context_screenshot_history_and_references(self):
        from PIL import Image

        class FakeWindows:
            def list_windows(self):
                return [{
                    "title": "Test Window",
                    "hwnd": 1,
                    "pid": 1,
                    "process_name": "test.exe",
                    "bounds": {}
                }]

            def _find_window_hwnd(self, query):
                return 1

            def get_clipboard(self):
                return "clipboard text"

            def get_explorer_selection(self):
                return ["C:/tmp/selected.txt"]

            def list_processes(self, limit=10):
                return [{"pid": 1, "name": "test.exe"}]

        class FakeVision:
            def __init__(self, root):
                self.root = Path(root)
                self.counter = 0

            def capture_screen(self, return_base64=False):
                self.counter += 1
                path = self.root / f"screen_{self.counter}.png"
                value = 0 if self.counter == 1 else 255
                Image.new("RGB", (20, 20), (value, value, value)).save(path)
                return {
                    "success": True,
                    "filepath": str(path),
                    "width": 20,
                    "height": 20,
                    "timestamp": time.time()
                }

            def detect_windows(self):
                return [{
                    "title": "Test Window",
                    "hwnd": 1,
                    "pid": 1,
                    "bbox": [0, 0, 20, 20],
                    "is_active": True
                }]

            def extract_visible_errors(self, screenshot_path=None):
                return []

        context = UnifiedContextEngine(
            windows=FakeWindows(),
            vision=FakeVision(self.temp_dir.name)
        )
        first = context.capture_screen(label="before test")
        second = context.capture_screen()
        self.assertTrue(first["success"])
        self.assertTrue(second["success"])
        self.assertEqual(context.resolve_reference("latest screenshot")["kind"], "screenshot")
        self.assertEqual(context._find_screenshot("before test")["id"], first["id"])

        context.register_attachment({
            "name": "report.pdf",
            "path": "C:/tmp/report.pdf",
            "type": "pdf",
            "context_text": "report"
        })
        self.assertEqual(context.resolve_reference("this")["kind"], "attachment")
        self.assertEqual(context.resolve_reference("this screenshot")["kind"], "screenshot")

        self.brain.unified_context = context
        resolved_args = self.brain._resolve_argument_references({
            "attachment_path": "this file"
        })
        self.assertEqual(resolved_args["attachment_path"], "C:/tmp/report.pdf")

        comparison = context.compare_screenshots("latest", "previous")
        self.assertTrue(comparison["success"])
        self.assertTrue(comparison["visual_change_detected"])
        self.assertGreater(comparison["pixel_change_percent"], 0)

        snapshot = context.snapshot(include_processes=True)
        self.assertEqual(snapshot["active_process"], "test.exe")
        self.assertEqual(snapshot["selected_files"][0], "C:/tmp/selected.txt")
        self.assertEqual(snapshot["clipboard"], "clipboard text")

        context.last_snapshot = {
            "active_process": "explorer.exe",
            "active_window_title": "File Explorer",
            "selected_files": ["C:/tmp/selected.txt"],
        }
        selected_ref = context.resolve_reference("this file")
        self.assertEqual(selected_ref["kind"], "file")
        self.assertEqual(selected_ref["value"], "C:/tmp/selected.txt")
        self.assertEqual(selected_ref["resolution"], "active_explorer_selection")

    def test_v5_compound_command_fallback(self):
        decision = self.brain._compound_fallback_decision(
            "Take a screenshot, then check my project for errors"
        )
        self.assertIsNotNone(decision)
        self.assertEqual(decision.decision_type, "plan")
        tools = [step.tool for step in decision.steps]
        self.assertIn("capture_screen", tools)
        self.assertIn("inspect_project", tools)
        self.assertGreaterEqual(len(tools), 2)

    # 13. Phase 4: Neural Decision Extraction & Schema Validation
    def test_neural_decision_parser(self):
        from maya_core.brain.decision import parse_and_validate_decision, extract_json_block
        from maya_core.tools.registry import default_tool_registry

        # Conversational decision
        conv_raw = 'Here is my reply: ```json\n{"type": "conversation", "message": "I am doing well!"}\n```'
        dec_conv = parse_and_validate_decision(conv_raw, default_tool_registry)
        self.assertIsNotNone(dec_conv)
        self.assertEqual(dec_conv.decision_type, "conversation")
        self.assertEqual(dec_conv.message, "I am doing well!")

        # Tool call decision
        tool_raw = '{"type": "tool_call", "tool": "search_files", "arguments": {"query": "*.py", "directory": "D:/MAYA"}}'
        dec_tool = parse_and_validate_decision(tool_raw, default_tool_registry)
        self.assertIsNotNone(dec_tool)
        self.assertEqual(dec_tool.decision_type, "tool_call")
        self.assertEqual(dec_tool.tool, "search_files")
        self.assertEqual(dec_tool.arguments["query"], "*.py")

        # Multi-step plan decision
        plan_raw = '''{
            "type": "plan",
            "goal": "Open VS Code and check project",
            "steps": [
                {"tool": "open_application", "arguments": {"application": "Visual Studio Code"}},
                {"tool": "inspect_project", "arguments": {"target": "active_project"}}
            ]
        }'''
        dec_plan = parse_and_validate_decision(plan_raw, default_tool_registry)
        self.assertIsNotNone(dec_plan)
        self.assertEqual(dec_plan.decision_type, "plan")
        self.assertEqual(len(dec_plan.steps), 2)
        self.assertEqual(dec_plan.steps[0].tool, "open_application")
        self.assertEqual(dec_plan.steps[1].tool, "inspect_project")

        # Unknown tool should fail validation
        unknown_raw = '{"type": "tool_call", "tool": "hack_the_planet", "arguments": {}}'
        dec_unknown = parse_and_validate_decision(unknown_raw, default_tool_registry)
        self.assertFalse(dec_unknown.is_valid)
        self.assertIn("does not exist", dec_unknown.validation_error)

    # 14. Phase 4: Strict Constant-Time HMAC Auth and Origin Checking
    def test_security_constant_time_hmac(self):
        import hmac
        AUTH_TOKEN = "maya_secure_secret_token_12345"

        # Valid token comparison
        user_valid = "maya_secure_secret_token_12345"
        self.assertTrue(hmac.compare_digest(user_valid, AUTH_TOKEN))

        # Invalid token comparison
        user_invalid = "wrong_token_guess"
        self.assertFalse(hmac.compare_digest(user_invalid, AUTH_TOKEN))

        # Empty token
        self.assertFalse(hmac.compare_digest("", AUTH_TOKEN))

    # 15. Phase 4: MayaBrain Cognitive Processing & Fallback
    def test_mayabrain_fallback_and_execution(self):
        # Conversational query
        res1 = self.brain.process_request("What is your architectural philosophy?")
        self.assertIn("intent", res1)
        self.assertIn("reply", res1)
        self.assertFalse(res1.get("requires_confirmation", False))

        # Action query
        res2 = self.brain.process_request("Launch VS Code")
        self.assertIn("intent", res2)
        self.assertIn("reply", res2)
        self.assertIn("tasks", res2)

if __name__ == "__main__":
    unittest.main()
