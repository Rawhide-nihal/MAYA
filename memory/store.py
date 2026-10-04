"""
MAYA Persistent Memory System V2
Multi-tier memory architecture: Working, Episodic, Semantic, Preference, Project, and Action memory.
Supports semantic retrieval, importance scoring, and conflict supersession.
"""
import sqlite3
import json
import time
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from maya_core.config import MEMORY_DB_PATH, PROJECT_ROOT

class MemoryStore:
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = Path(db_path) if db_path else MEMORY_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(str(self.db_path))
        try:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversation_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    role TEXT NOT NULL,
                    message TEXT NOT NULL,
                    timestamp REAL,
                    metadata TEXT
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS semantic_memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT NOT NULL,
                    key TEXT NOT NULL,
                    content TEXT NOT NULL,
                    importance REAL DEFAULT 1.0,
                    confidence REAL DEFAULT 1.0,
                    version INTEGER DEFAULT 1,
                    superseded INTEGER DEFAULT 0,
                    timestamp REAL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS working_memory (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at REAL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS project_memory (
                    project_name TEXT PRIMARY KEY,
                    project_path TEXT NOT NULL,
                    language TEXT,
                    build_system TEXT,
                    active_branch TEXT,
                    known_issues TEXT,
                    last_opened REAL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS episodic_memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL,
                    source TEXT NOT NULL,
                    importance REAL DEFAULT 1.0,
                    timestamp REAL
                )
            """)
            conn.commit()

            # Seed initial preferences if empty
            cursor.execute("SELECT COUNT(*) FROM semantic_memory")
            if cursor.fetchone()[0] == 0:
                defaults = [
                    ("preference", "browser", "User prefers Google Chrome", 4.0),
                    ("preference", "editor", "User works primarily in VS Code", 4.0),
                    ("system", "os", "Windows 11 with PowerShell terminal", 5.0),
                ]
                for cat, key, val, imp in defaults:
                    cursor.execute("""
                        INSERT INTO semantic_memory (category, key, content, importance, confidence, version, superseded, timestamp)
                        VALUES (?, ?, ?, ?, 1.0, 1, 0, ?)
                    """, (cat, key, val, imp, time.time()))

                cursor.execute("""
                    INSERT OR IGNORE INTO project_memory (project_name, project_path, language, build_system, active_branch, known_issues, last_opened)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, ("MAYA", str(PROJECT_ROOT), "Python / TypeScript", "Vite / npm", "main", "None", time.time()))
                conn.commit()
        finally:
            conn.close()

    def add_message(self, role: str, message: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        conn = sqlite3.connect(str(self.db_path))
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO conversation_history (role, message, timestamp, metadata)
                VALUES (?, ?, ?, ?)
            """, (role, message, time.time(), json.dumps(metadata) if metadata else None))
            conn.commit()
        finally:
            conn.close()

        # Update working memory and memory extraction pipeline
        if role == "user":
            self.set_working_memory("last_user_input", message)
            self._extract_candidate_memories(message)
        elif role == "maya":
            self.set_working_memory("last_maya_output", message)

    def get_conversation_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM conversation_history ORDER BY id DESC LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()
            ordered = list(reversed(rows))
            return [{
                "id": r["id"],
                "role": r["role"],
                "message": r["message"],
                "timestamp": r["timestamp"],
                "metadata": json.loads(r["metadata"]) if r["metadata"] else {}
            } for r in ordered]
        finally:
            conn.close()

    def set_working_memory(self, key: str, value: Any) -> None:
        conn = sqlite3.connect(str(self.db_path))
        try:
            cursor = conn.cursor()
            val_str = json.dumps(value) if isinstance(value, (dict, list)) else str(value)
            cursor.execute("""
                INSERT OR REPLACE INTO working_memory (key, value, updated_at)
                VALUES (?, ?, ?)
            """, (key, val_str, time.time()))
            conn.commit()
        finally:
            conn.close()

    def get_working_memory(self, key: str, default: Any = None) -> Any:
        conn = sqlite3.connect(str(self.db_path))
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM working_memory WHERE key = ?", (key,))
            row = cursor.fetchone()
            if row:
                try:
                    return json.loads(row[0])
                except Exception:
                    return row[0]
            return default
        finally:
            conn.close()

    def _extract_candidate_memories(self, text: str) -> None:
        """Memory Extraction Pipeline: checks for user preferences or key facts."""
        lower = text.lower()

        # Preference extraction
        match_pref = re.search(r"\bi\s+(?:prefer|like|always use|switched to)\s+([a-zA-Z0-9\s\.\-_]+)", lower)
        if match_pref:
            item = match_pref.group(1).strip()
            if any(term in item for term in ["chrome", "firefox", "edge", "vscode", "vs code", "pycharm", "dark", "light"]):
                key = "browser" if any(b in item for b in ["chrome", "firefox", "edge"]) else "editor"
                self.save_semantic_memory("preference", key, f"User prefers {item.title()}", importance=4.0)

        # Working on project
        match_proj = re.search(r"\b(?:working on|developing|building)\s+(?:my\s+)?([a-zA-Z0-9\s\.\-_]+)", lower)
        if match_proj:
            proj_name = match_proj.group(1).strip()
            self.save_episodic_memory(f"User mentioned working on: {proj_name}", source="chat", importance=3.5)

    def save_semantic_memory(self, category: str, key: str, content: str, importance: float = 3.0) -> None:
        """Saves semantic fact with conflict supersession."""
        conn = sqlite3.connect(str(self.db_path))
        try:
            cursor = conn.cursor()
            # Supersede old versions for the same key
            cursor.execute("""
                UPDATE semantic_memory 
                SET superseded = 1 
                WHERE category = ? AND key = ? AND superseded = 0
            """, (category, key))
            cursor.execute("""
                INSERT INTO semantic_memory (category, key, content, importance, confidence, version, superseded, timestamp)
                VALUES (?, ?, ?, ?, 1.0, 1, 0, ?)
            """, (category, key, content, importance, time.time()))
            conn.commit()
        finally:
            conn.close()

    def save_episodic_memory(self, content: str, source: str = "system", importance: float = 2.0) -> None:
        conn = sqlite3.connect(str(self.db_path))
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO episodic_memory (content, source, importance, timestamp)
                VALUES (?, ?, ?, ?)
            """, (content, source, importance, time.time()))
            conn.commit()
        finally:
            conn.close()

    def get_all_memories(self) -> Dict[str, Any]:
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM semantic_memory WHERE superseded = 0 ORDER BY timestamp DESC")
            semantic = [dict(r) for r in cursor.fetchall()]

            cursor.execute("SELECT * FROM project_memory ORDER BY last_opened DESC")
            projects = [dict(r) for r in cursor.fetchall()]

            cursor.execute("SELECT * FROM episodic_memory ORDER BY timestamp DESC LIMIT 40")
            episodic = [dict(r) for r in cursor.fetchall()]

            return {
                "semantic": semantic,
                "projects": projects,
                "episodic": episodic
            }
        finally:
            conn.close()

    def search_relevant_memories(self, query: str, top_k: int = 3) -> List[str]:
        """TF-IDF Cosine Similarity semantic retrieval over active memories."""
        all_mems = self.get_all_memories()
        documents = []
        for s in all_mems["semantic"]:
            documents.append(f"{s['category']} {s['key']}: {s['content']}")
        for e in all_mems["episodic"]:
            documents.append(f"Event: {e['content']}")

        if not documents:
            return []

        try:
            vec = TfidfVectorizer().fit(documents + [query])
            doc_vecs = vec.transform(documents)
            query_vec = vec.transform([query])
            sims = cosine_similarity(query_vec, doc_vecs).flatten()
            ranked_indices = sims.argsort()[::-1]
            results = []
            for idx in ranked_indices[:top_k]:
                if sims[idx] > 0.1:
                    results.append(documents[idx])
            return results
        except Exception:
            return documents[:top_k]

    def update_project(self, name: str, path: str, language: str, build_system: str, branch: str = "main", issues: str = "None") -> None:
        conn = sqlite3.connect(str(self.db_path))
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO project_memory 
                (project_name, project_path, language, build_system, active_branch, known_issues, last_opened)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (name, path, language, build_system, branch, issues, time.time()))
            conn.commit()
        finally:
            conn.close()
