"""
MAYA Core Unit and Integration Tests
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from maya_core.models.base import DeterministicIntentClassifier
from security.permissions.tier import PermissionManager, PermissionLevel
from security.audit.ledger import ActionLedger, ActionRecord
from memory.store import MemoryStore
from agents.windows.agent import WindowsAgent
from agents.filesystem.agent import FileAgent
from agents.developer.agent import DeveloperAgent
from agents.diagnostics.engine import DiagnosticEngine

class TestMayaCore(unittest.TestCase):
    def setUp(self):
        self.classifier = DeterministicIntentClassifier()
        self.permissions = PermissionManager(PermissionLevel.LEVEL_2_SAFE_ACTION)
        self.ledger = ActionLedger(db_path="d:\\MAYA\\test_audit.db")
        self.memory = MemoryStore(db_path="d:\\MAYA\\test_memory.db")
        self.windows = WindowsAgent()
        self.filesystem = FileAgent()
        self.developer = DeveloperAgent()
        self.diagnostics = DiagnosticEngine()

    def test_intent_classification(self):
        res1 = self.classifier.classify_and_extract("Hey Maya")
        self.assertEqual(res1["intent"], "CHAT")
        self.assertIsNone(res1["tool"])

        res2 = self.classifier.classify_and_extract("Open VS Code")
        self.assertEqual(res2["intent"], "PC_ACTION")
        self.assertEqual(res2["tool"], "open_application")

        res3 = self.classifier.classify_and_extract("Scan my PC")
        self.assertEqual(res3["intent"], "SYSTEM_DIAGNOSTIC")
        self.assertEqual(res3["tool"], "run_system_diagnostics")

    def test_permission_enforcement(self):
        # Observation tool should be granted
        p1 = self.permissions.check_permission("get_system_status", {})
        self.assertTrue(p1.granted)
        self.assertFalse(p1.requires_confirmation)

        # Critical tool must require confirmation
        p2 = self.permissions.check_permission("delete_file", {"filepath": "important.txt"})
        self.assertFalse(p2.granted)
        self.assertTrue(p2.requires_confirmation)
        self.assertIsNotNone(p2.confirmation_id)

    def test_memory_storage_and_search(self):
        self.memory.save_semantic_memory("preferences", "test_pref", "User likes dark mode theme", 3.0)
        mems = self.memory.search_relevant_memories("dark mode")
        self.assertTrue(len(mems) > 0)
        self.assertTrue(any("dark mode" in m.lower() for m in mems))

    def test_real_diagnostics(self):
        diag = self.diagnostics.run_full_diagnostics()
        self.assertIn("status", diag)
        self.assertIn("metrics", diag)
        self.assertGreater(diag["metrics"]["cpu_percent"], -1)
        self.assertGreater(diag["metrics"]["ram_percent"], 0)

    def tearDown(self):
        for f in ["d:\\MAYA\\test_audit.db", "d:\\MAYA\\test_memory.db"]:
            if os.path.exists(f):
                try:
                    os.remove(f)
                except Exception:
                    pass

if __name__ == "__main__":
    unittest.main()
