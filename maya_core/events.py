"""
MAYA Canonical Event Names & Schema
Centralized event definitions ensuring strict synchronization between Python backend,
SSE event stream, and Desktop GUI (React/TypeScript).
"""

# Maya Core Agent Lifecycle States
MAYA_STATE_CHANGED = "maya.state.changed"

# Dynamic Task Planner & Plan Progression
TASK_PLAN_CREATED = "task.plan.created"
TASK_STEP_STARTED = "task.step.started"
TASK_STEP_COMPLETED = "task.step.completed"
TASK_STEP_FAILED = "task.step.failed"
TASK_COMPLETED = "task.completed"
TASK_FAILED = "task.failed"
TASK_CANCELLED = "task.cancelled"

# Security & Permission Gate
PERMISSION_REQUESTED = "permission.requested"
PERMISSION_RESOLVED = "permission.resolved"

# Action Ledger & Rollback
ACTION_RECORDED = "action.recorded"
ACTION_ROLLED_BACK = "action.rolled_back"

# Voice & Speech Engine
VOICE_LISTENING_STARTED = "voice.listening.started"
VOICE_LISTENING_AMPLITUDE = "voice.listening.amplitude"
VOICE_LISTENING_COMPLETED = "voice.listening.completed"
VOICE_LISTENING_STOPPED = "voice.listening.stopped"
VOICE_SPEAKING_STARTED = "voice.speaking.started"
VOICE_SPEAKING_AMPLITUDE = "voice.speaking.amplitude"
VOICE_SPEAKING_COMPLETED = "voice.speaking.completed"

# Vision & Screen Context
VISION_SCREEN_CAPTURED = "vision.screen.captured"
VISION_ANALYSIS_COMPLETED = "vision.analysis.completed"
