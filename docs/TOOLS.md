# MAYA Tool Interface Specification

All tools in MAYA are strongly typed and deterministic. Tools return structured dictionaries and record their results in the Action Ledger.

## Declared Tools

### 1. `open_application`
- **Description**: Finds executable binary from PATH, registry, or standard installation paths, starts detached process, and verifies launch.
- **Permission Level**: Level 2 (Safe Action).
- **Arguments**:
  ```json
  { "application": "Visual Studio Code" }
  ```

### 2. `inspect_project`
- **Description**: Discovers workspace language, detects build systems (npm, Maven, Gradle, Poetry), validates configurations, and checks syntax.
- **Permission Level**: Level 1 (Observation).
- **Arguments**:
  ```json
  { "target": "active_project" }
  ```

### 3. `run_system_diagnostics`
- **Description**: Scans CPU, RAM, disk space, network gateway connectivity, and developer CLI tools.
- **Permission Level**: Level 1 (Observation).
- **Arguments**:
  ```json
  { "depth": "full" }
  ```

### 4. `clean_temp_files`
- **Description**: Safely cleans stale files (>24 hours old) from `%TEMP%`.
- **Permission Level**: Level 3 (Modification).
- **Arguments**: `{}`

### 5. `rollback_last_action`
- **Description**: Reverts the most recent reversible action from the Action Ledger.
- **Permission Level**: Level 2 (Safe Action).
- **Arguments**:
  ```json
  { "action_id": "optional_id" }
  ```
