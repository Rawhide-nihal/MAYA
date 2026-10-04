# MAYA Developer Guide

This document outlines how to develop, test, and extend MAYA.

## Development Setup

### Backend (Python)
Dependencies are preconfigured using Python 3.10+:
- `psutil` (system & process metrics)
- `Flask` (REST API & IPC)
- `scikit-learn` (vector retrieval & memory ranking)
- `pillow`, `pygetwindow` (vision & window detection)
- `pyttsx3` (voice engine)

To run the backend server in development mode:
```powershell
python maya_server.py
```

### Desktop Frontend (React + Vite + Electron)
Located in `apps/desktop`:
```powershell
cd apps/desktop
npm run dev
```

To run as an Electron desktop window:
```powershell
npx electron apps/desktop
```

### Running Tests
```powershell
# Run unit and integration tests
python -m unittest tests/test_core.py

# Run evaluation suite
python training/evaluation/eval_suite.py
```

## Adding a New Skill
1. Define tool functions in `agents/` or `tools/`.
2. Map tool to an appropriate `PermissionLevel` in `security/permissions/tier.py`.
3. Register skill entry in `skills/registry.py`:
   ```python
   MayaSkill(
       id="custom_skill",
       name="Custom Skill",
       version="1.0.0",
       category="Productivity",
       description="Description of functionality",
       permission_level=2,
       tools=["custom_tool_name"]
   )
   ```
4. Expose the tool handler inside `TaskPlanner.execute_tool` in `maya_core/planner/task_planner.py`.
