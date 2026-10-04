# MAYA Security Architecture

MAYA enforces a strict security perimeter where the AI model is treated as untrusted input. The language model never has direct raw access to operating-system APIs.

```
AI Model / User Request
          │
          ▼
Structured Tool Invocation
          │
          ▼
Deterministic Permission Gate (tier.py)
   ├── Level <= Allowed? -> Execute Tool
   └── Level > Allowed or Level 4? -> Generate Confirmation Request
          │
          ▼
Tool Execution (WindowsAgent / FileAgent)
          │
          ▼
Action Ledger (Immutable SQLite Audit Trail)
```

## Security Guardrails
1. **No Arbitrary Elevated Code**: High-risk system modification (registry changes, disk formatting, account manipulation) is blocked at Level 4 and cannot be initiated autonomously.
2. **Path Traversal Prevention**: File access is strictly constrained to authorized user directories.
3. **No Credential Ingestion**: Secrets, tokens, and credentials are never stored in conversational memory or injected into prompts.
4. **Deterministic Gate**: The permission policy is enforced in hardcoded Python application logic, not by asking the LLM if an action is safe.
