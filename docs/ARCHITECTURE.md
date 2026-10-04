# MAYA Architecture Overview

```
                               ┌────────────────────────────────┐
                               │     MAYA Desktop Frontend      │
                               │  React + Vite + Tailwind + GL  │
                               └──────────────┬─────────────────┘
                                              │ HTTP / IPC
                               ┌──────────────▼─────────────────┐
                               │    Core API & Event Server     │
                               │        (maya_server.py)        │
                               └──────────────┬─────────────────┘
                                              │
                      ┌───────────────────────┴───────────────────────┐
                      │                                               │
           ┌──────────▼──────────┐                         ┌──────────▼──────────┐
           │     Model Router    │                         │    Task Planner     │
           │  (Local/Fine-Tuned) │                         │ (Understand -> Act) │
           └──────────┬──────────┘                         └──────────┬──────────┘
                      │                                               │
       ┌──────────────┴──────────────┐                 ┌──────────────┴──────────────┐
       │                             │                 │                             │
┌──────▼──────┐               ┌──────▼──────┐   ┌──────▼──────┐               ┌──────▼──────┐
│ MemoryStore │               │ IntentModel │   │ Permissions │               │Action Ledger│
│  (SQLite)   │               │ (Sub-msec)  │   │ (Levels 0-4)│               │  (Rollback) │
└─────────────┘               └─────────────┘   └──────┬──────┘               └─────────────┘
                                                       │
                                      ┌────────────────┴────────────────┐
                                      │                                 │
                               ┌──────▼──────┐                   ┌──────▼──────┐
                               │Windows Agent│                   │ File Agent  │
                               └──────┬──────┘                   └──────┬──────┘
                               │                                 │
                               ┌──────▼──────┐                   ┌──────▼──────┐
                               │  Dev Agent  │                   │ Diagnostics │
                               └─────────────┘                   └─────────────┘
```

## System Subsystems

### 1. Intent & Routing Layer
Before any computer tool is executed, user queries pass through the `DeterministicIntentClassifier`. This guarantees that casual conversations (e.g. *"I hate how slow Chrome is"*) are never mistakenly converted into destructive actions, while explicit commands (e.g. *"Open VS Code"*) are mapped directly to typed tool calls.

### 2. Task Planner Loop
Executes: **Understand → Plan → Act → Observe → Verify → Report**.
Command execution is never considered successful until verified by checking process tables, window titles, or compiler return codes.

### 3. Agent Subsystems
- **Windows Agent**: Application path resolution from PATH, Registry, and standard directories; process lifecycle management; active window tracking.
- **Terminal Agent**: Non-interactive PowerShell and CMD runner with structured metrics: command, stdout, stderr, exit code, execution time.
- **File Agent**: High-performance recursive search with standard directory exclusions (`node_modules`, `.git`, `.venv`), content reading, atomic writing, and temp directory cleanup.
- **Developer Agent**: Ecosystem detection (Python, TypeScript, Java, Rust), configuration validation, syntax compilation, and error diagnosis.
- **Diagnostic Engine**: Real-time hardware and software telemetry with prioritization into `Healthy`, `Information`, `Recommendation`, `Warning`, and `Critical`.
- **Vision Agent**: Screen grabbing and window geometry detection.
