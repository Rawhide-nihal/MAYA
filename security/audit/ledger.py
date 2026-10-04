"""
MAYA Action Ledger & Rollback System
Records every meaningful state-changing operation with undo capability.
"""
import sqlite3
import json
import time
import os
import shutil
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "maya_audit.db")

@dataclass
class ActionRecord:
    action_id: str
    tool_name: str
    arguments: Dict[str, Any]
    affected_resources: List[str]
    previous_state: Optional[Dict[str, Any]]
    result: Dict[str, Any]
    undo_available: bool
    status: str  # success, failed, undone
    timestamp: float
    summary: str

class ActionLedger:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = os.path.abspath(db_path)
        self._init_db()

    def _init_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS action_ledger (
                    action_id TEXT PRIMARY KEY,
                    tool_name TEXT NOT NULL,
                    arguments TEXT,
                    affected_resources TEXT,
                    previous_state TEXT,
                    result TEXT,
                    undo_available INTEGER,
                    status TEXT,
                    timestamp REAL,
                    summary TEXT
                )
            """)
            conn.commit()

    def record_action(self, record: ActionRecord) -> None:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO action_ledger 
                (action_id, tool_name, arguments, affected_resources, previous_state, result, undo_available, status, timestamp, summary)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record.action_id,
                record.tool_name,
                json.dumps(record.arguments),
                json.dumps(record.affected_resources),
                json.dumps(record.previous_state) if record.previous_state else None,
                json.dumps(record.result),
                1 if record.undo_available else 0,
                record.status,
                record.timestamp,
                record.summary
            ))
            conn.commit()

    def get_recent_actions(self, limit: int = 10) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
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
                    "tool_name": row["tool_name"],
                    "arguments": json.loads(row["arguments"]) if row["arguments"] else {},
                    "affected_resources": json.loads(row["affected_resources"]) if row["affected_resources"] else [],
                    "previous_state": json.loads(row["previous_state"]) if row["previous_state"] else None,
                    "result": json.loads(row["result"]) if row["result"] else {},
                    "undo_available": bool(row["undo_available"]),
                    "status": row["status"],
                    "timestamp": row["timestamp"],
                    "summary": row["summary"]
                })
            return results

    def rollback_last_action(self) -> Dict[str, Any]:
        """Attempt rollback of the most recent reversible action."""
        recent = self.get_recent_actions(limit=5)
        for act in recent:
            if act["undo_available"] and act["status"] == "success":
                return self.rollback_action(act["action_id"])
        return {"success": False, "message": "No reversible action found."}

    def rollback_action(self, action_id: str) -> Dict[str, Any]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM action_ledger WHERE action_id = ?", (action_id,))
            row = cursor.fetchone()
            if not row:
                return {"success": False, "message": f"Action {action_id} not found."}

            if not row["undo_available"]:
                return {"success": False, "message": "This action is not reversible."}

            tool_name = row["tool_name"]
            prev_state = json.loads(row["previous_state"]) if row["previous_state"] else None
            args = json.loads(row["arguments"]) if row["arguments"] else {}

            # Execute specific rollback based on tool
            try:
                if tool_name == "move_file" and prev_state and "original_path" in prev_state:
                    dest = args.get("destination")
                    orig = prev_state["original_path"]
                    if os.path.exists(dest):
                        shutil.move(dest, orig)
                elif tool_name == "write_file" and prev_state and "original_content" in prev_state:
                    filepath = args.get("filepath")
                    with open(filepath, "w", encoding="utf-8") as f:
                        f.write(prev_state["original_content"])
                elif tool_name == "create_directory":
                    dirpath = args.get("directory_path")
                    if os.path.exists(dirpath) and not os.listdir(dirpath):
                        os.rmdir(dirpath)

                # Mark as undone
                cursor.execute("UPDATE action_ledger SET status = 'undone', undo_available = 0 WHERE action_id = ?", (action_id,))
                conn.commit()
                return {"success": True, "message": f"Action {action_id} ({tool_name}) successfully rolled back."}
            except Exception as e:
                return {"success": False, "message": f"Rollback failed: {str(e)}"}
