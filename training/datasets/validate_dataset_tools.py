"""
MAYA Dataset Tool Validation Engine
Scans training, validation, and test datasets and asserts that every
referenced tool call and plan step strictly exists in MAYA's ToolRegistry.
Fails with exit code 1 if any undefined tool is found.
"""
import sys
import json
from pathlib import Path
from typing import Dict, Any, List, Set

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from maya_core.tools.registry import default_tool_registry
from maya_core.brain.decision import extract_json_block
from typing import Dict, Any, List, Set, Tuple
from security.permissions.tier import TOOL_PERMISSION_MAP

DATASETS_DIR = PROJECT_ROOT / "training" / "datasets"

def validate_dataset_file(filepath: Path) -> Tuple[int, List[str]]:
    if not filepath.exists():
        return 0, [f"File not found: {filepath.name}"]

    errors = []
    sample_count = 0

    with open(filepath, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            sample_count += 1
            try:
                sample = json.loads(line)
            except Exception as e:
                errors.append(f"Line {line_num}: JSON syntax error: {e}")
                continue

            def _validate_tool_instance(tool_name: str, args: Dict[str, Any], context_label: str):
                tool_schema = default_tool_registry.get(tool_name)
                if not tool_schema:
                    errors.append(f"Line {line_num} ({context_label}): Unknown tool '{tool_name}' (not in ToolRegistry)")
                    return
                # 1. Verify executor exists
                if tool_schema.execution_handler is None or not callable(tool_schema.execution_handler):
                    errors.append(f"Line {line_num} ({context_label}): Tool '{tool_name}' lacks callable execution handler")
                # 2. Verify permission mapping exists
                if tool_name not in TOOL_PERMISSION_MAP or tool_schema.permission_level is None:
                    errors.append(f"Line {line_num} ({context_label}): Tool '{tool_name}' lacks permission tier mapping")
                # 3. Verify arguments against parameter schema
                if isinstance(args, dict):
                    valid, err = tool_schema.validate_arguments(args)
                    if not valid:
                        errors.append(f"Line {line_num} ({context_label}): Invalid arguments for '{tool_name}': {err}")

            # Check messages for tool calls
            for msg in sample.get("messages", []):
                if msg.get("role") == "assistant":
                    content = msg.get("content", "")
                    parsed = extract_json_block(content)
                    if parsed:
                        dec_type = parsed.get("type")
                        if dec_type == "tool_call":
                            tool = parsed.get("tool")
                            args = parsed.get("arguments", {})
                            if tool:
                                _validate_tool_instance(tool, args, "assistant tool_call")
                        elif dec_type == "plan":
                            for step_idx, step in enumerate(parsed.get("steps", []), 1):
                                s_tool = step.get("tool")
                                s_args = step.get("arguments", {})
                                if s_tool:
                                    _validate_tool_instance(s_tool, s_args, f"plan step {step_idx}")

            # Check explicit expected field if present
            expected = sample.get("expected", {})
            if expected.get("tool"):
                tool = expected["tool"]
                args = expected.get("arguments", {})
                _validate_tool_instance(tool, args, "expected tool")

    return sample_count, errors

def main():
    print("=" * 65)
    print("MAYA DATASET TOOL SCHEMA VALIDATOR")
    print("=" * 65)

    valid_tools = set(default_tool_registry.get_tool_names())
    print(f"[Registry] Loaded {len(valid_tools)} verified canonical tools:")
    for t in sorted(valid_tools):
        print(f"  • {t}")

    files_to_check = ["train.jsonl", "val.jsonl", "test.jsonl", "maya_sft_dataset.jsonl"]
    total_errors = []
    total_samples = 0

    print("\n[Validation] Checking dataset files...")
    for filename in files_to_check:
        filepath = DATASETS_DIR / filename
        count, errors = validate_dataset_file(filepath)
        if count > 0:
            status = "PASSED" if not errors else f"FAILED ({len(errors)} errors)"
            print(f"  • {filename:<25} : {count:>5} samples -> {status}")
            total_samples += count
            total_errors.extend(errors)

    print("-" * 65)
    if total_errors:
        print(f"[FAILED] Found {len(total_errors)} tool consistency errors:")
        for err in total_errors[:10]:
            print(f"  - {err}")
        if len(total_errors) > 10:
            print(f"  ... and {len(total_errors) - 10} more.")
        sys.exit(1)
    else:
        print(f"[SUCCESS] All tools across {total_samples} samples strictly exist in ToolRegistry!")
        sys.exit(0)

if __name__ == "__main__":
    from typing import Tuple
    main()
