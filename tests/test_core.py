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
from maya_core.personality.engine import PersonalityEngine, MayaMode, ResponseDepth
from maya_core.context.engine import UnifiedContextEngine
from maya_core.attachments.intelligence import AttachmentIntelligence

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
        self.assertIn("tool.started", event_names)
        self.assertIn("tool.completed", event_names)
        self.assertIn("task.completed", event_names)

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
