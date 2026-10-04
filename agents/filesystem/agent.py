"""
MAYA Filesystem Agent
High-performance, safe filesystem interaction, search, cleanup, and file manipulation.
"""
import os
import shutil
import glob
import time
from typing import Dict, Any, List, Optional

class FileAgent:
    EXCLUDED_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".idea", ".vscode"}

    def __init__(self):
        pass

    def search_files(self, query: str, search_path: str = "d:\\MAYA", max_results: int = 25) -> List[Dict[str, Any]]:
        matches = []
        query_lower = query.lower()
        search_path = os.path.abspath(search_path)

        if not os.path.exists(search_path):
            return []

        for root, dirs, files in os.walk(search_path):
            dirs[:] = [d for d in dirs if d not in self.EXCLUDED_DIRS]
            for file in files:
                if query_lower in file.lower():
                    full_path = os.path.join(root, file)
                    try:
                        stat = os.stat(full_path)
                        matches.append({
                            "name": file,
                            "path": full_path,
                            "size_bytes": stat.st_size,
                            "size_kb": round(stat.st_size / 1024, 2),
                            "modified": stat.st_mtime
                        })
                        if len(matches) >= max_results:
                            return matches
                    except Exception:
                        continue
        return matches

    def read_file(self, filepath: str, max_chars: int = 10000) -> Dict[str, Any]:
        filepath = os.path.abspath(filepath)
        if not os.path.exists(filepath):
            return {"success": False, "error": f"File does not exist: {filepath}"}

        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                content = f.read(max_chars)
            return {
                "success": True,
                "filepath": filepath,
                "content": content,
                "truncated": len(content) >= max_chars
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def write_file(self, filepath: str, content: str) -> Dict[str, Any]:
        filepath = os.path.abspath(filepath)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        prev_content = None
        if os.path.exists(filepath):
            try:
                with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                    prev_content = f.read()
            except Exception:
                pass

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            return {
                "success": True,
                "filepath": filepath,
                "bytes_written": len(content.encode("utf-8")),
                "previous_content": prev_content
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def move_file(self, source: str, destination: str) -> Dict[str, Any]:
        source = os.path.abspath(source)
        destination = os.path.abspath(destination)
        if not os.path.exists(source):
            return {"success": False, "error": f"Source does not exist: {source}"}

        try:
            os.makedirs(os.path.dirname(destination), exist_ok=True)
            shutil.move(source, destination)
            return {
                "success": True,
                "source": source,
                "destination": destination,
                "previous_path": source
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def clean_temp_files(self) -> Dict[str, Any]:
        """Safely cleans stale files from the user's temp directory"""
        temp_dir = os.environ.get("TEMP", os.environ.get("TMP", "C:\\Windows\\Temp"))
        cleaned_bytes = 0
        cleaned_count = 0
        skipped = 0

        try:
            for item in os.listdir(temp_dir):
                item_path = os.path.join(temp_dir, item)
                try:
                    # Only remove files older than 24 hours to prevent deleting in-use process locks
                    if time.time() - os.path.getmtime(item_path) > 86400:
                        if os.path.isfile(item_path) or os.path.islink(item_path):
                            size = os.path.getsize(item_path)
                            os.remove(item_path)
                            cleaned_bytes += size
                            cleaned_count += 1
                except Exception:
                    skipped += 1
                    continue
            
            mb_cleared = round(cleaned_bytes / (1024 * 1024), 2)
            gb_cleared = round(mb_cleared / 1024, 2)
            summary = f"Cleared {gb_cleared} GB ({mb_cleared} MB) across {cleaned_count} temporary files."
            return {
                "success": True,
                "cleaned_files": cleaned_count,
                "bytes_freed": cleaned_bytes,
                "mb_freed": mb_cleared,
                "summary": summary
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
