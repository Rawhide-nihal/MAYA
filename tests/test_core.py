"""
MAYA Phase 2 — Comprehensive Core & Integration Test Suite
Tests Brain, Dynamic Planner, Memory Store V2, Permissions V2, Action Ledger with Rollback,
Hardware Telemetry, and Model Runtime.
"""
import os
import gc
import sys
import tempfile
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

    # 2. Permissions V2 Enforcement & Single-Use Tokens
    def test_permission_tier_enforcement(self):
        # Read-only observation is granted under Level 2
        p_read = self.permissions.check_permission("get_system_status", {})
        self.assertTrue(p_read.granted)
        self.assertFalse(p_read.requires_confirmation)

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

if __name__ == "__main__":
    unittest.main()
