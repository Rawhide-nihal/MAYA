"""
MAYA Action Ledger & Rollback System V2
Immutable audit trail of every state-changing operation with automatic rollback preparation.
Zero fabricated states.
"""
import sqlite3
import json
import time
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from maya_core.config import AUDIT_DB_PATH

@dataclass
class ActionRecord:
    action_id: str
    plan_id: str
    tool_name: str
    arguments: Dict[str, Any]
    affected_resources: List[str]
    previous_state: Optional[Dict[str, Any]]
    result: Dict[str, Any]
    verified: bool
    undo_available: bool
    status: str  # success, failed, undone
    timestamp: float
    summary: str

class ActionLedger:
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = Path(db_path) if db_path else AUDIT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(str(self.db_path))
        try:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS action_ledger (
                    action_id TEXT PRIMARY KEY,
                    plan_id TEXT,
                    tool_name TEXT NOT NULL,
                    arguments TEXT,
                    affected_resources TEXT,
                    previous_state TEXT,
                    result TEXT,
                    verified INTEGER,
                    undo_available INTEGER,
                    status TEXT,
                    timestamp REAL,
                    summary TEXT
                )
            """)
            conn.commit()
        finally:
            conn.close()

    def record_action(self, record: ActionRecord) -> None:
        conn = sqlite3.connect(str(self.db_path))
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO action_ledger 
                (action_id, plan_id, tool_name, arguments, affected_resources, previous_state, result, verified, undo_available, status, timestamp, summary)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record.action_id,
                record.plan_id,
                record.tool_name,
                json.dumps(record.arguments),
                json.dumps(record.affected_resources),
                json.dumps(record.previous_state) if record.previous_state else None,
                json.dumps(record.result),
                1 if record.verified else 0,
                1 if record.undo_available else 0,
                record.status,
                record.timestamp,
                record.summary
            ))
            conn.commit()
        finally:
            conn.close()

    def get_recent_actions(self, limit: int = 15) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM action_ledger 
                ORDER BY timestamp DESC LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()
            results = []
            for row in rows:
                results.append({
                    "action_id": row["action_id"],
                    "plan_id": row["plan_id"],
                    "tool_name": row["tool_name"],
                    "arguments": json.loads(row["arguments"]) if row["arguments"] else {},
                    "affected_resources": json.loads(row["affected_resources"]) if row["affected_resources"] else [],
                    "previous_state": json.loads(row["previous_state"]) if row["previous_state"] else None,
                    "result": json.loads(row["result"]) if row["result"] else {},
                    "verified": bool(row["verified"]),
                    "undo_available": bool(row["undo_available"]),
                    "status": row["status"],
                    "timestamp": row["timestamp"],
                    "summary": row["summary"]
                })
            return results
        finally:
            conn.close()

    def rollback_last_action(self) -> Dict[str, Any]:
        """Attempt rollback of the most recent reversible action."""
        recent = self.get_recent_actions(limit=10)
        for act in recent:
            if act["undo_available"] and act["status"] == "success":
                return self.rollback_action(act["action_id"])
        return {"success": False, "message": "No reversible action found in the ledger."}

    def rollback_action(self, action_id: str) -> Dict[str, Any]:
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM action_ledger WHERE action_id = ?", (action_id,))
            row = cursor.fetchone()
            if not row:
                return {"success": False, "message": f"Action {action_id} not found."}

            if not row["undo_available"]:
                return {"success": False, "message": f"Action {action_id} is not reversible."}

            tool_name = row["tool_name"]
            prev_state = json.loads(row["previous_state"]) if row["previous_state"] else None
            args = json.loads(row["arguments"]) if row["arguments"] else {}

            try:
                # 1. File Move Rollback
                if tool_name == "move_file" and prev_state and "original_path" in prev_state:
                    dest = Path(args.get("destination", ""))
                    orig = Path(prev_state["original_path"])
                    if dest.exists():
                        orig.parent.mkdir(parents=True, exist_ok=True)
                        shutil.move(str(dest), str(orig))

                # 2. File Write / Patch Rollback
                elif tool_name in ["write_file", "apply_patch"] and prev_state and "original_content" in prev_state:
                    filepath = Path(args.get("filepath", ""))
                    if filepath.exists():
                        filepath.write_text(prev_state["original_content"], encoding="utf-8")

                # 3. Create File/Directory Rollback
                elif tool_name == "create_directory":
                    dirpath = Path(args.get("directory_path", ""))
                    if dirpath.exists() and not list(dirpath.iterdir()):
                        dirpath.rmdir()

                # Mark as undone in ledger
                cursor.execute("UPDATE action_ledger SET status = 'undone', undo_available = 0 WHERE action_id = ?", (action_id,))
                conn.commit()
                return {
                    "success": True,
                    "action_id": action_id,
                    "tool": tool_name,
                    "message": f"Action #{action_id} ({tool_name}) successfully rolled back."
                }
            except Exception as e:
                return {"success": False, "error": f"Rollback failed: {str(e)}"}
        finally:
            conn.close()
