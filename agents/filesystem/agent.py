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

    def list_directory(self, path: Optional[str] = None) -> Dict[str, Any]:
        """Lists directory entries with file sizes and modification timestamps."""
        target = self._resolve_search_path(path)
        if not target.exists() or not target.is_dir():
            return {"success": False, "error": f"Directory not found: {target}"}

        items = []
        try:
            for entry in os.scandir(str(target)):
                try:
                    stat = entry.stat()
                    items.append({
                        "name": entry.name,
                        "is_dir": entry.is_dir(),
                        "size_bytes": stat.st_size if not entry.is_dir() else 0,
                        "size_kb": round(stat.st_size / 1024, 2) if not entry.is_dir() else 0,
                        "modified": stat.st_mtime
                    })
                except Exception:
                    continue
            items.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))
            return {
                "success": True,
                "directory": str(target),
                "count": len(items),
                "items": items[:100]
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def copy_file(self, source: str, destination: str) -> Dict[str, Any]:
        """Copies file or directory to destination and verifies."""
        s = Path(source).resolve()
        d = Path(destination).resolve()
        if not s.exists():
            return {"success": False, "error": f"Source does not exist: {s}"}

        try:
            if s.is_dir():
                if d.exists():
                    d = d / s.name
                shutil.copytree(str(s), str(d))
            else:
                d.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(s), str(d))

            verified = d.exists()
            return {
                "success": verified,
                "source": str(s),
                "destination": str(d),
                "verified": verified,
                "previous_state": {"copied_destination": str(d)}
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def delete_file(self, filepath: str, permanent: bool = False) -> Dict[str, Any]:
        """Safely deletes a file with automatic undo snapshot caching."""
        p = Path(filepath).resolve()
        if not p.exists():
            return {"success": False, "error": f"Target does not exist: {p}"}

        undo_cache_dir = CACHE_DIR / "undo_trash"
        undo_cache_dir.mkdir(parents=True, exist_ok=True)
        backup_path = undo_cache_dir / f"{int(time.time())}_{p.name}"

        try:
            # Preserve backup snapshot for rollback
            if p.is_file():
                shutil.copy2(str(p), str(backup_path))
                os.remove(str(p))
            else:
                shutil.copytree(str(p), str(backup_path))
                shutil.rmtree(str(p))

            verified = not p.exists()
            return {
                "success": verified,
                "filepath": str(p),
                "verified": verified,
                "backup_snapshot": str(backup_path) if backup_path.exists() else None,
                "previous_state": {"backup_snapshot": str(backup_path), "original_path": str(p)},
                "message": f"Deleted '{p.name}'." if verified else f"Failed to confirm deletion of '{p.name}'."
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
