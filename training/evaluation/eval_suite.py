import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from maya_core.models.base import DeterministicIntentClassifier
from security.permissions.tier import PermissionManager, PermissionLevel

def run_evaluation():
    classifier = DeterministicIntentClassifier()
    permissions = PermissionManager(PermissionLevel.LEVEL_2_SAFE_ACTION)

    test_cases = [
        {"input": "Hey Maya.", "expected_intent": "CHAT", "expected_tool": None},
        {"input": "Open VS Code", "expected_intent": "PC_ACTION", "expected_tool": "open_application"},
        {"input": "Open VS Code and check my project", "expected_intent": "DEVELOPMENT_ACTION", "expected_tool": "open_application_and_inspect"},
        {"input": "Scan my PC", "expected_intent": "SYSTEM_DIAGNOSTIC", "expected_tool": "run_system_diagnostics"},
        {"input": "I hate how slow Chrome has become", "expected_intent": "SUGGESTION", "expected_tool": None},
        {"input": "Maya, undo that", "expected_intent": "PC_ACTION", "expected_tool": "rollback_last_action"},
        {"input": "What did you just do?", "expected_intent": "INFORMATION_REQUEST", "expected_tool": "get_recent_actions"}
    ]

    passed = 0
    print("=" * 60)
    print("Running MAYA Evaluation Suite...")
    print("=" * 60)

    for i, tc in enumerate(test_cases, 1):
        res = classifier.classify_and_extract(tc["input"])
        intent_match = res["intent"] == tc["expected_intent"]
        tool_match = res["tool"] == tc["expected_tool"]
        success = intent_match and tool_match
        if success:
            passed += 1
            print(f"[{i}/{len(test_cases)}] PASS: '{tc['input']}' -> {res['intent']} (Tool: {res['tool']})")
        else:
            print(f"[{i}/{len(test_cases)}] FAIL: '{tc['input']}' -> Got {res['intent']}, expected {tc['expected_intent']}")

    # Test safety / permission rejection
    crit_perm = permissions.check_permission("delete_file", {"filepath": "C:\\Windows\\System32"})
    safety_pass = crit_perm.requires_confirmation is True
    print(f"Safety Rejection Check: {'PASS' if safety_pass else 'FAIL'}")

    acc = (passed / len(test_cases)) * 100
    print("-" * 60)
    print(f"Final Accuracy: {acc:.1f}% ({passed}/{len(test_cases)} passed)")
    print("=" * 60)
    return passed == len(test_cases) and safety_pass

if __name__ == "__main__":
    run_evaluation()
