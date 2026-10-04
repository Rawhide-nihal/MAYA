"""
MAYA Persistent Memory System
Provides episodic, semantic, project, user-preference, and conversation memory with semantic retrieval.
"""
import sqlite3
import json
import time
import os
import re
from typing import List, Dict, Any, Optional
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "maya_memory.db")

class MemoryStore:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = os.path.abspath(db_path)
        self._init_db()

    def _init_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
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
                    key TEXT UNIQUE NOT NULL,
                    content TEXT NOT NULL,
                    importance REAL DEFAULT 1.0,
                    timestamp REAL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS project_memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_name TEXT UNIQUE NOT NULL,
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
                    source TEXT,
                    importance REAL,
                    timestamp REAL
                )
            """)
            conn.commit()

        # Seed initial memory if empty
        self._seed_initial_memory()

    def _seed_initial_memory(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM semantic_memory")
            if cursor.fetchone()[0] == 0:
                defaults = [
                    ("preferences", "preferred_editor", "Visual Studio Code", 4.0),
                    ("preferences", "response_style", "Concise and direct for simple questions, detailed for technical investigations", 4.0),
                    ("facts", "primary_os", "Windows 11 PC", 5.0),
                    ("workflows", "dev_workflow", "Understand -> Plan -> Act -> Observe -> Verify -> Report", 5.0)
                ]
                for cat, key, val, imp in defaults:
                    cursor.execute("""
                        INSERT OR IGNORE INTO semantic_memory (category, key, content, importance, timestamp)
                        VALUES (?, ?, ?, ?, ?)
                    """, (cat, key, val, imp, time.time()))
                
                # Seed default project if exists
                cursor.execute("""
                    INSERT OR IGNORE INTO project_memory (project_name, project_path, language, build_system, active_branch, known_issues, last_opened)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, ("MAYA Desktop Companion", "d:\\MAYA", "TypeScript / Python", "Vite / npm", "main", "None", time.time()))
                conn.commit()

    def add_message(self, role: str, message: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO conversation_history (role, message, timestamp, metadata)
                VALUES (?, ?, ?, ?)
            """, (role, message, time.time(), json.dumps(metadata) if metadata else None))
            conn.commit()
        # Trigger memory extraction pipeline
        if role == "user":
            self._extract_candidate_memories(message)

    def get_conversation_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM conversation_history ORDER BY id ASC LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()
            return [{
                "id": r["id"],
                "role": r["role"],
                "message": r["message"],
                "timestamp": r["timestamp"],
                "metadata": json.loads(r["metadata"]) if r["metadata"] else {}
            } for r in rows]

    def _extract_candidate_memories(self, text: str) -> None:
        """Memory Extraction Pipeline: extraction -> importance -> deduplication -> storage"""
        lower = text.lower()
        if "i prefer" in lower or "my favorite" in lower:
            key = f"pref_{int(time.time())}"
            self.save_semantic_memory("preferences", key, text, importance=3.5)
        elif "working on" in lower or "my project" in lower:
            self.save_episodic_memory(f"User mentioned working on: {text}", source="chat", importance=3.0)

    def save_semantic_memory(self, category: str, key: str, content: str, importance: float = 3.0) -> None:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO semantic_memory (category, key, content, importance, timestamp)
                VALUES (?, ?, ?, ?, ?)
            """, (category, key, content, importance, time.time()))
            conn.commit()

    def save_episodic_memory(self, content: str, source: str = "system", importance: float = 2.0) -> None:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO episodic_memory (content, source, importance, timestamp)
                VALUES (?, ?, ?, ?)
            """, (content, source, importance, time.time()))
            conn.commit()

    def get_all_memories(self) -> Dict[str, Any]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM semantic_memory ORDER BY timestamp DESC")
            semantic = [dict(r) for r in cursor.fetchall()]
            
            cursor.execute("SELECT * FROM project_memory ORDER BY last_opened DESC")
            projects = [dict(r) for r in cursor.fetchall()]
            
            cursor.execute("SELECT * FROM episodic_memory ORDER BY timestamp DESC LIMIT 50")
            episodic = [dict(r) for r in cursor.fetchall()]
            
            return {
                "semantic": semantic,
                "projects": projects,
                "episodic": episodic
            }

    def search_relevant_memories(self, query: str, top_k: int = 3) -> List[str]:
        """TF-IDF Cosine Similarity semantic search over stored memories"""
        all_mems = self.get_all_memories()
        documents = []
        doc_map = []
        for s in all_mems["semantic"]:
            text = f"{s['category']}: {s['content']}"
            documents.append(text)
            doc_map.append(text)
        for e in all_mems["episodic"]:
            text = f"Event: {e['content']}"
            documents.append(text)
            doc_map.append(text)

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
                    results.append(doc_map[idx])
            return results
        except Exception:
            return documents[:top_k]

    def update_project(self, name: str, path: str, language: str, build_system: str, branch: str = "main", issues: str = "None") -> None:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO project_memory 
                (project_name, project_path, language, build_system, active_branch, known_issues, last_opened)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (name, path, language, build_system, branch, issues, time.time()))
            conn.commit()
