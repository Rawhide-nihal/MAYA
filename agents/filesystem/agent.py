"""
MAYA Filesystem Agent V2
Advanced filesystem exploration, content search, duplicate detection, hashing, and safe manipulations.
Target paths default to user directories rather than hard-coded project paths.
"""
import os
import shutil
import hashlib
import zipfile
import time
import difflib
from pathlib import Path
from typing import Dict, Any, List, Optional
from maya_core.config import PROJECT_ROOT, CACHE_DIR

class FileAgent:
    EXCLUDED_DIRS = {
        ".git", "node_modules", ".venv", "venv", "__pycache__",
        "dist", "build", ".idea", ".vscode", "AppData"
    }

    def __init__(self, default_search_root: Optional[Path] = None):
        self.default_search_root = default_search_root or Path.home()

    def _resolve_search_path(self, target: Optional[str]) -> Path:
        if not target or target.strip() in [".", "workspace", "project"]:
            return PROJECT_ROOT
        t_path = Path(target)
        if t_path.is_absolute() and t_path.exists():
            return t_path
        # Check standard user locations
        user_dirs = {
            "downloads": Path.home() / "Downloads",
            "documents": Path.home() / "Documents",
            "desktop": Path.home() / "Desktop",
            "home": Path.home(),
            "projects": PROJECT_ROOT.parent
        }
        low = target.lower().strip()
        if low in user_dirs and user_dirs[low].exists():
            return user_dirs[low]
        # Check relative to project root
        cand = PROJECT_ROOT / target
        if cand.exists():
            return cand
        return self.default_search_root

    def search_files(
        self,
        query: str,
        directory: Optional[str] = None,
        file_ext: Optional[str] = None,
        max_results: int = 25
    ) -> List[Dict[str, Any]]:
        """Search files using exact, partial, or fuzzy name matching."""
        search_dir = self._resolve_search_path(directory)
        matches = []
        q_lower = query.lower().strip()

        if not search_dir.exists():
            return []

        for root, dirs, files in os.walk(str(search_dir)):
            dirs[:] = [d for d in dirs if d not in self.EXCLUDED_DIRS and not d.startswith(".")]
            for file in files:
                f_lower = file.lower()
                if file_ext and not f_lower.endswith(file_ext.lower()):
                    continue

                is_match = q_lower in f_lower
                if not is_match and len(q_lower) >= 3:
                    # Fuzzy match check
                    ratio = difflib.SequenceMatcher(None, q_lower, f_lower).ratio()
                    is_match = ratio > 0.65

                if is_match:
                    full_p = Path(root) / file
                    try:
                        stat = full_p.stat()
                        matches.append({
                            "name": file,
                            "path": str(full_p),
                            "size_bytes": stat.st_size,
                            "size_kb": round(stat.st_size / 1024, 2),
                            "modified": stat.st_mtime
                        })
                        if len(matches) >= max_results:
                            return matches
                    except Exception:
                        continue
        return matches

    def search_file_content(
        self,
        query: str,
        directory: Optional[str] = None,
        file_ext: Optional[str] = None,
        max_matches: int = 15
    ) -> List[Dict[str, Any]]:
        """Searches file contents (grep) for code symbols, text, or errors."""
        search_dir = self._resolve_search_path(directory)
        results = []
        q_lower = query.lower()

        allowed_text_exts = {".py", ".ts", ".tsx", ".js", ".jsx", ".json", ".md", ".txt", ".html", ".css", ".toml", ".yaml", ".yml", ".xml", ".java"}

        for root, dirs, files in os.walk(str(search_dir)):
            dirs[:] = [d for d in dirs if d not in self.EXCLUDED_DIRS and not d.startswith(".")]
            for file in files:
                p = Path(root) / file
                if p.suffix.lower() not in allowed_text_exts:
                    continue
                if file_ext and p.suffix.lower() != file_ext.lower():
                    continue

                try:
                    with open(p, "r", encoding="utf-8", errors="ignore") as f:
                        for line_idx, line in enumerate(f, 1):
                            if q_lower in line.lower():
                                results.append({
                                    "file": file,
                                    "path": str(p),
                                    "line_number": line_idx,
                                    "line": line.strip()[:200]
                                })
                                if len(results) >= max_matches:
                                    return results
                except Exception:
                    continue
        return results

    def find_largest_files(self, directory: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        """Identifies large disk space consumers."""
        search_dir = self._resolve_search_path(directory)
        entries = []
        for root, dirs, files in os.walk(str(search_dir)):
            dirs[:] = [d for d in dirs if d not in self.EXCLUDED_DIRS]
            for file in files:
                fp = Path(root) / file
                try:
                    sz = fp.stat().st_size
                    entries.append({"name": file, "path": str(fp), "size_mb": round(sz / (1024**2), 2), "size_bytes": sz})
                except Exception:
                    continue
        entries.sort(key=lambda x: x["size_bytes"], reverse=True)
        return entries[:limit]

    def find_duplicates(self, directory: Optional[str] = None, min_size_kb: int = 10) -> List[Dict[str, Any]]:
        """Detects duplicate files by comparing file hashes."""
        search_dir = self._resolve_search_path(directory)
        hashes: Dict[str, str] = {}
        duplicates = []

        for root, dirs, files in os.walk(str(search_dir)):
            dirs[:] = [d for d in dirs if d not in self.EXCLUDED_DIRS]
            for file in files:
                fp = Path(root) / file
                try:
                    if fp.stat().st_size < min_size_kb * 1024:
                        continue
                    # Compute quick md5
                    hasher = hashlib.md5()
                    with open(fp, "rb") as f:
                        hasher.update(f.read(65536))
                    h = hasher.hexdigest()
                    if h in hashes:
                        duplicates.append({
                            "original": hashes[h],
                            "duplicate": str(fp),
                            "name": file
                        })
                    else:
                        hashes[h] = str(fp)
                except Exception:
                    continue
        return duplicates

    def read_file(self, filepath: str, max_chars: int = 15000) -> Dict[str, Any]:
        p = Path(filepath).resolve()
        if not p.exists():
            return {"success": False, "error": f"File does not exist: {p}"}

        try:
            with open(p, "r", encoding="utf-8", errors="replace") as f:
                content = f.read(max_chars)
            return {
                "success": True,
                "filepath": str(p),
                "content": content,
                "truncated": len(content) >= max_chars
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def write_file(self, filepath: str, content: str) -> Dict[str, Any]:
        p = Path(filepath).resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        prev_content = None
        if p.exists():
            try:
                prev_content = p.read_text(encoding="utf-8", errors="replace")
            except Exception:
                pass

        try:
            p.write_text(content, encoding="utf-8")
            return {
                "success": True,
                "filepath": str(p),
                "bytes_written": len(content.encode("utf-8")),
                "previous_content": prev_content
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def move_file(self, source: str, destination: str) -> Dict[str, Any]:
        s = Path(source).resolve()
        d = Path(destination).resolve()
        if not s.exists():
            return {"success": False, "error": f"Source does not exist: {s}"}

        try:
            d.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(s), str(d))
            # Strict Action Verification
            verified = not s.exists() and d.exists()
            return {
                "success": verified,
                "source": str(s),
                "destination": str(d),
                "verified": verified,
                "previous_path": str(s)
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def clean_temp_files(self) -> Dict[str, Any]:
        """Safely cleans stale files (>24 hours) from the Windows temp directory."""
        temp_dir = os.environ.get("TEMP", os.environ.get("TMP", "C:\\Windows\\Temp"))
        cleaned_bytes = 0
        cleaned_count = 0

        try:
            for item in os.listdir(temp_dir):
                item_path = os.path.join(temp_dir, item)
                try:
                    if time.time() - os.path.getmtime(item_path) > 86400:
                        if os.path.isfile(item_path) or os.path.islink(item_path):
                            sz = os.path.getsize(item_path)
                            os.remove(item_path)
                            cleaned_bytes += sz
                            cleaned_count += 1
                except Exception:
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
