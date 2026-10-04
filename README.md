# MAYA — Personal AI Desktop Companion

> **A real, modular, trainable, conversational desktop AI companion living inside your Windows PC.**

MAYA is not a scripted chatbot, fake simulation, or simple wrapper around an external API. She is an intelligent operating companion built to understand your requests, create deterministic task plans, control applications, inspect development projects, diagnose system performance, remember your preferences across sessions, and execute authorized operations while verifying every action.

---

## Visual Source of Truth

MAYA's desktop user interface faithfully replicates the cyberpunk midnight glassmorphic design:
- **Central Animated AI Core**: Multi-layered glowing plasma orb with rotating cosmic energy rings, horizontal flowing audio waves, and dynamic state ladders (`LISTENING`, `THINKING`, `EXECUTING`, `RESPONDING`, `ANALYZE`, `PLAN`, `EXECUTE`, `VERIFY`).
- **Left Navigation Sidebar**: Maya branding with online indicator, navigation tabs (`Chat`, `Projects`, `PC Control`, `Memory`, `Skills`, `Activity`, `Settings`), and Maya Pro status card.
- **Right PC Control Panel**: Real-time task progress cards, recent action history, and live system metrics (CPU, RAM, Storage, GPU) with animated sparkline wave charts.

---

## Key Capabilities

1. **Conversational AI & Personality Engine**: Friendly, calm, technically capable, and honest. Operates on the rule: *"Know it, remember it, investigate it, or say that it is unknown."*
2. **Deterministic Task Planning**: Follows the operational loop: **Understand → Plan → Act → Observe → Verify → Report**.
3. **Native Windows PC Control**:
   - Launches and verifies applications (e.g. Visual Studio Code, Notepad, Chrome, Windows Explorer, Terminal).
   - Monitors running processes with genuine CPU and memory utilization.
   - Cleans temporary files safely from `%TEMP%`.
4. **Developer Workspace Diagnostics**:
   - Detects project languages (Python, TypeScript, Node.js, Java, Rust) and build systems (Vite, npm, Maven, Gradle, Poetry).
   - Scans source code and configuration files for genuine syntax and structural errors.
5. **System Diagnostic Engine**:
   - Real hardware, performance, storage, network, and development environment health scans.
   - Prioritizes findings into `Healthy`, `Information`, `Recommendation`, `Warning`, and `Critical`.
6. **Multi-Tier Security & Action Ledger**:
   - Enforces 5 deterministic permission levels (Level 0 through Level 4).
   - Maintains an immutable SQLite Action Ledger with full rollback / undo capability (`"Maya, undo that"`).
7. **Persistent Memory System**:
   - Short-term conversational context, episodic event logging, semantic facts, project tracking, and TF-IDF cosine-similarity retrieval.
8. **Trainable AI Model Stack**:
   - Model router supporting local fine-tuned adapters (LoRA/QLoRA), local LLM endpoints (Ollama, llama.cpp), and optional cloud fallbacks.
   - Includes training dataset (`training/datasets/maya_sft_dataset.jsonl`) and fine-tuning pipeline (`training/finetuning/train_lora.py`).

---

## Quick Start

### Prerequisites
- Windows 10/11
- Python 3.10+
- Node.js 18+ and npm

### 1. Start MAYA Desktop App
Run the master production launcher:
```powershell
python start_maya.py
```
This automatically boots the core Python API backend on port 5000 and displays the desktop companion window.

Alternatively, to run in Vite development mode:
```powershell
# Terminal 1: Python Backend
python maya_server.py

# Terminal 2: Vite Desktop Frontend
cd apps/desktop
npm run dev
```

### 2. Run Tests & Evaluation Suite
```powershell
# Run unit and integration tests
python -m unittest tests/test_core.py

# Run model evaluation suite
python training/evaluation/eval_suite.py
```

---

## Project Structure
```text
MAYA/
├── apps/
│   └── desktop/               # React + TypeScript + Vite + Tailwind + Electron frontend
│       ├── electron/          # Electron desktop frame & preload
│       └── src/
│           ├── components/    # MayaCoreCanvas, Sidebar, RightPanel, ChatStage, etc.
│           └── services/      # Backend API bridge
├── maya_core/
│   ├── models/                # ModelProvider, LocalModel, MayaFineTuned, IntentClassifier
│   ├── router/                # ModelRouter (local/offline routing)
│   ├── personality/           # Maya personality specification & prompt builder
│   └── planner/               # TaskPlanner (Understand -> Plan -> Act -> Observe -> Verify -> Report)
├── agents/
│   ├── windows/               # WindowsAgent (application launch & process management)
│   ├── terminal/              # TerminalAgent (PowerShell/CMD execution)
│   ├── filesystem/            # FileAgent (search, read, write, move, temp cleanup)
│   ├── developer/             # DeveloperAgent (workspace inspection & compiler checks)
│   ├── diagnostics/           # DiagnosticEngine (system telemetry & prioritized checks)
│   └── vision/                # VisionAgent (screenshots & window detection)
├── memory/                    # MemoryStore (episodic, semantic, projects, TF-IDF search)
├── security/
│   ├── permissions/           # Deterministic PermissionManager (Levels 0 - 4)
│   └── audit/                 # ActionLedger (SQLite persistence & rollback)
├── training/
│   ├── datasets/              # Supervised fine-tuning dataset (maya_sft_dataset.jsonl)
│   ├── finetuning/            # train_lora.py (HuggingFace PEFT fine-tuning pipeline)
│   └── evaluation/            # eval_suite.py (intent & safety evaluation)
├── docs/                      # Complete architecture & subsystem documentation
├── maya_server.py             # Core Flask REST & IPC server
├── gui_launcher.py            # PyQt6-WebEngine native desktop window runner
└── start_maya.py              # Master production launcher
```

---

## Documentation
- [Architecture](docs/ARCHITECTURE.md)
- [Model Stack](docs/MODEL.md)
- [Training & Fine-Tuning](docs/TRAINING.md)
- [Memory Architecture](docs/MEMORY.md)
- [Tool Interface](docs/TOOLS.md)
- [Security Architecture](docs/SECURITY.md)
- [Permissions Policy](docs/PERMISSIONS.md)
- [Development Guide](docs/DEVELOPMENT.md)
- [Roadmap](docs/ROADMAP.md)
