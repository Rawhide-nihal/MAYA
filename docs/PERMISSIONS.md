# MAYA Action Permission Policy

MAYA defines five explicit permission levels (`PermissionLevel` in `security/permissions/tier.py`):

| Level | Name | Scope & Allowed Operations | Confirmation Required |
|---|---|---|---|
| **0** | **Conversation** | Pure conversational assistance. No PC tools or filesystem access. | None |
| **1** | **Observation** | Read system status, process telemetry, search files, read logs, screen inspect. | None |
| **2** | **Safe Action** | Launch recognized apps (VS Code, Chrome), directory creation, harmless build diagnostics. | Default Allowed |
| **3** | **Modification** | Edit existing files, move data, terminate processes, clean temp files. | Configurable Gate |
| **4** | **Critical** | Permanent deletion, system settings, registry edits, firewall changes. | **Always Required** |

## Confirmation Workflow
When an action exceeds the user's active tier or requires Level 4 privileges:
1. `PermissionManager` intercepts the request.
2. A unique `confirmation_id` is generated with description and parameters.
3. The desktop UI presents an interactive confirmation modal.
4. Tool execution is halted until explicit user authorization is provided.
