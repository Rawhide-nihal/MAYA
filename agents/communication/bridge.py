"""Thread-safe command bridge between MAYA Core and the MAYA Chrome extension."""
from __future__ import annotations

import threading
import time
import uuid
import mimetypes
import os
import json
import re
import unicodedata
from difflib import SequenceMatcher
from collections import deque
from typing import Any, Deque, Dict, Optional, List

from maya_core.config import MAYA_DATA_DIR


class CommunicationBridge:
    def __init__(self):
        self._lock = threading.RLock()
        self._queues: Dict[str, Deque[str]] = {
            "gmail": deque(),
            "whatsapp": deque(),
            "telegram": deque(),
        }
        self._commands: Dict[str, Dict[str, Any]] = {}
        self._events: Dict[str, threading.Event] = {}
        self._results: Dict[str, Dict[str, Any]] = {}
        self._last_extension_seen: Optional[float] = None
        self._browser_context: Dict[str, Any] = {}
        self._browser_actions: Deque[str] = deque()
        self._browser_action_payloads: Dict[str, Dict[str, Any]] = {}
        self._browser_action_events: Dict[str, threading.Event] = {}
        self._browser_action_results: Dict[str, Dict[str, Any]] = {}
        self._contacts_path = MAYA_DATA_DIR / "communication_contacts.json"
        self._contacts: Dict[str, Dict[str, Dict[str, Any]]] = {
            "whatsapp": {},
            "telegram": {},
            "gmail": {},
        }
        self._load_contacts()

    @staticmethod
    def _normalize_contact_name(value: str) -> str:
        return re.sub(r"\s+", " ", str(value or "").strip()).casefold()

    @staticmethod
    def _normalize_search_text(value: str) -> str:
        raw = unicodedata.normalize("NFKD", str(value or ""))
        raw = "".join(ch for ch in raw if not unicodedata.combining(ch))
        raw = raw.casefold()
        raw = re.sub(r"[^a-z0-9@.+]+", " ", raw)
        return re.sub(r"\s+", " ", raw).strip()

    @staticmethod
    def _tokens(value: str) -> List[str]:
        return [token for token in CommunicationBridge._normalize_search_text(value).split(" ") if token]

    @staticmethod
    def _levenshtein_distance(a: str, b: str) -> int:
        if a == b:
            return 0
        if not a:
            return len(b)
        if not b:
            return len(a)
        if len(a) > len(b):
            a, b = b, a
        previous = list(range(len(a) + 1))
        for i, char_b in enumerate(b, start=1):
            current = [i]
            for j, char_a in enumerate(a, start=1):
                insert_cost = current[j - 1] + 1
                delete_cost = previous[j] + 1
                replace_cost = previous[j - 1] + (char_a != char_b)
                current.append(min(insert_cost, delete_cost, replace_cost))
            previous = current
        return previous[-1]

    @staticmethod
    def _ngrams(value: str, n: int = 3) -> set:
        text = CommunicationBridge._normalize_search_text(value).replace(" ", "")
        if not text:
            return set()
        if len(text) <= n:
            return {text}
        return {text[i:i+n] for i in range(len(text) - n + 1)}

    @staticmethod
    def _normalize_phone(value: str) -> str:
        raw = str(value or "").strip()
        if not raw:
            return ""
        digits = re.sub(r"\D+", "", raw)
        return digits

    @classmethod
    def _contact_type_from_jid(cls, jid: str, explicit_type: str = "") -> str:
        explicit = str(explicit_type or "").strip().lower()
        if explicit in {"contact", "group", "unknown"}:
            if explicit != "unknown":
                return explicit
        jid_lower = str(jid or "").lower()
        if "@g.us" in jid_lower:
            return "group"
        if any(domain in jid_lower for domain in ("@c.us", "@s.whatsapp.net")):
            return "contact"
        return explicit or "unknown"

    @classmethod
    def _phone_from_jid(cls, jid: str) -> str:
        raw = str(jid or "").strip()
        match = re.match(r"^(\d+)@(?:c\.us|s\.whatsapp\.net)$", raw, flags=re.IGNORECASE)
        return match.group(1) if match else ""

    @classmethod
    def _record_key(cls, record: Dict[str, Any]) -> str:
        jid = str(record.get("jid") or record.get("chat_id") or "").strip().casefold()
        if jid:
            return f"jid:{jid}"
        phone = cls._normalize_phone(record.get("phone") or "")
        if phone:
            return f"phone:{phone}"
        name = cls._normalize_contact_name(record.get("name") or record.get("display_name") or "")
        record_type = str(record.get("type") or "unknown").lower()
        return f"name:{name}:{record_type}"

    def _coerce_contact_record(
        self,
        item: Any,
        *,
        service: str,
        source: str,
        now: float,
    ) -> Optional[Dict[str, Any]]:
        if isinstance(item, dict):
            name = str(item.get("name") or item.get("display_name") or item.get("title") or "").strip()
            jid = str(item.get("jid") or item.get("chat_id") or item.get("id") or "").strip()
            phone = self._normalize_phone(item.get("phone") or "")
            record_type = self._contact_type_from_jid(jid, str(item.get("type") or ""))
            aliases = item.get("aliases") or []
            if isinstance(aliases, str):
                aliases = [aliases]
        else:
            name = str(item or "").strip()
            jid = ""
            phone = ""
            record_type = "unknown"
            aliases = []

        if not phone and jid:
            phone = self._phone_from_jid(jid)

        reserved = {
            "new chat", "search", "archived", "communities", "status",
            "channels", "settings", "profile", "new group", "contacts",
            "frequently contacted", "recent chats"
        }
        normalized_name = self._normalize_contact_name(name)
        if (
            not normalized_name
            or len(name) > 160
            or normalized_name in reserved
            or normalized_name.startswith("http")
        ):
            return None

        clean_aliases = []
        seen_aliases = set()
        for alias in [name, *list(aliases)]:
            alias_text = str(alias or "").strip()
            alias_key = self._normalize_contact_name(alias_text)
            if alias_key and alias_key not in seen_aliases:
                seen_aliases.add(alias_key)
                clean_aliases.append(alias_text)

        return {
            "service": service,
            "name": name,
            "display_name": name,
            "jid": jid or None,
            "chat_id": jid or None,
            "phone": phone or None,
            "type": record_type,
            "aliases": clean_aliases,
            "source": source,
            "first_seen": now,
            "last_seen": now,
            "last_synced": now,
        }

    def _merge_contact_records(
        self,
        existing: Dict[str, Any],
        incoming: Dict[str, Any],
        *,
        source: str,
        now: float,
    ) -> Dict[str, Any]:
        merged = dict(existing)
        old_name = str(existing.get("name") or "").strip()
        new_name = str(incoming.get("name") or "").strip()

        if new_name:
            merged["name"] = new_name
            merged["display_name"] = new_name

        for key in ("jid", "chat_id", "phone"):
            if incoming.get(key):
                merged[key] = incoming.get(key)

        incoming_type = str(incoming.get("type") or "unknown").lower()
        if incoming_type != "unknown" or not merged.get("type"):
            merged["type"] = incoming_type

        aliases = []
        seen = set()
        for alias in [
            *(existing.get("aliases") or []),
            old_name,
            *(incoming.get("aliases") or []),
            new_name,
        ]:
            alias_text = str(alias or "").strip()
            alias_key = self._normalize_contact_name(alias_text)
            if alias_key and alias_key not in seen:
                seen.add(alias_key)
                aliases.append(alias_text)
        merged["aliases"] = aliases

        merged["service"] = incoming.get("service") or existing.get("service")
        merged["source"] = source
        merged["first_seen"] = float(existing.get("first_seen") or now)
        merged["last_seen"] = now
        merged["last_synced"] = now
        return merged

    def _load_contacts(self) -> None:
        try:
            if not self._contacts_path.exists():
                return
            raw = json.loads(self._contacts_path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                return

            migrated: Dict[str, Dict[str, Dict[str, Any]]] = {
                "whatsapp": {},
                "telegram": {},
                "gmail": {},
            }
            now = time.time()

            for service in migrated:
                service_data = raw.get(service, {})
                if not isinstance(service_data, dict):
                    continue

                for old_key, old_record in service_data.items():
                    if not isinstance(old_record, dict):
                        old_record = {"name": str(old_record or old_key)}
                    candidate = self._coerce_contact_record(
                        old_record,
                        service=service,
                        source=str(old_record.get("source") or "legacy_cache"),
                        now=float(old_record.get("last_seen") or now),
                    )
                    if not candidate:
                        continue
                    candidate["first_seen"] = float(old_record.get("first_seen") or candidate["first_seen"])
                    candidate["last_seen"] = float(old_record.get("last_seen") or candidate["last_seen"])
                    candidate["last_synced"] = float(old_record.get("last_synced") or candidate["last_seen"])
                    key = self._record_key(candidate)
                    if key in migrated[service]:
                        migrated[service][key] = self._merge_contact_records(
                            migrated[service][key],
                            candidate,
                            source=str(candidate.get("source") or "legacy_cache"),
                            now=float(candidate.get("last_seen") or now),
                        )
                    else:
                        migrated[service][key] = candidate

            self._contacts = migrated
            self._save_contacts()
        except Exception:
            # A damaged local cache must never stop MAYA from starting.
            pass

    def _save_contacts(self) -> None:
        """Atomically persist the private local contact/group index."""
        try:
            self._contacts_path.parent.mkdir(parents=True, exist_ok=True)
            payload = dict(self._contacts)
            payload["_meta"] = {
                "schema_version": 2,
                "updated_at": time.time(),
            }
            temp_path = self._contacts_path.with_suffix(".json.tmp")
            temp_path.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False),
                encoding="utf-8"
            )
            os.replace(temp_path, self._contacts_path)
        except Exception:
            try:
                temp_path = self._contacts_path.with_suffix(".json.tmp")
                if temp_path.exists():
                    temp_path.unlink()
            except Exception:
                pass

    def update_contacts(
        self,
        service: str,
        contacts: List[Any],
        source: str = "browser",
    ) -> Dict[str, Any]:
        service_name = str(service or "").lower().strip()
        if service_name not in self._contacts:
            return {
                "success": False,
                "verified": False,
                "error": f"Unsupported contact service: {service_name}",
            }

        now = time.time()
        added = 0
        updated = 0
        merged_duplicates = 0
        persistent_change = False

        with self._lock:
            store = self._contacts[service_name]

            for item in contacts or []:
                incoming = self._coerce_contact_record(
                    item,
                    service=service_name,
                    source=source,
                    now=now,
                )
                if not incoming:
                    continue

                key = self._record_key(incoming)
                existing = store.get(key)

                # If richer JID/phone information arrives later, merge the
                # previous names-only record instead of creating a duplicate.
                if existing is None and (incoming.get("jid") or incoming.get("phone")):
                    incoming_names = {
                        self._normalize_contact_name(incoming.get("name") or ""),
                        *{
                            self._normalize_contact_name(a)
                            for a in (incoming.get("aliases") or [])
                        },
                    }
                    for old_key, candidate in list(store.items()):
                        if candidate.get("jid") or candidate.get("phone"):
                            continue
                        candidate_names = {
                            self._normalize_contact_name(candidate.get("name") or ""),
                            *{
                                self._normalize_contact_name(a)
                                for a in (candidate.get("aliases") or [])
                            },
                        }
                        if incoming_names.intersection(candidate_names):
                            existing = store.pop(old_key)
                            merged_duplicates += 1
                            persistent_change = True
                            break

                if existing:
                    merged = self._merge_contact_records(
                        existing,
                        incoming,
                        source=source,
                        now=now,
                    )
                    new_key = self._record_key(merged)
                    if new_key != key and key in store:
                        store.pop(key, None)
                    store[new_key] = merged
                    updated += 1
                    persistent_change = True
                else:
                    store[key] = incoming
                    added += 1
                    persistent_change = True

            if persistent_change:
                self._save_contacts()

            values = list(store.values())
            groups_total = sum(1 for r in values if r.get("type") == "group")
            contacts_total = sum(1 for r in values if r.get("type") == "contact")
            unknown_total = sum(1 for r in values if r.get("type") == "unknown")

        return {
            "success": True,
            "verified": True,
            "service": service_name,
            "added": added,
            "updated": updated,
            "merged_duplicates": merged_duplicates,
            "total": len(values),
            "contacts_total": contacts_total,
            "groups_total": groups_total,
            "unknown_total": unknown_total,
        }

    def list_contacts(
        self,
        service: str = "whatsapp",
        limit: int = 500,
        record_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        service_name = str(service or "").lower().strip()
        with self._lock:
            values = [dict(v) for v in self._contacts.get(service_name, {}).values()]

        if record_type:
            type_lower = str(record_type).lower().strip()
            values = [v for v in values if str(v.get("type") or "unknown").lower() == type_lower]

        values.sort(key=lambda item: (
            -float(item.get("last_seen", 0) or 0),
            str(item.get("name", "")).casefold()
        ))
        return values[:max(1, min(int(limit), 5000))]

    def resolve_contact(
        self,
        service: str,
        query: str,
        record_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Resolve a contact/group through several deterministic search structures:
        exact hash maps, token inverted index, prefix index, substring scan,
        trigram index, SequenceMatcher and Levenshtein edit distance.
        """
        service_name = str(service or "").lower().strip()
        normalized = self._normalize_search_text(query)
        phone_query = self._normalize_phone(query)
        query_tokens = set(self._tokens(query))
        query_grams = self._ngrams(query)

        with self._lock:
            records = [dict(v) for v in self._contacts.get(service_name, {}).values()]

        if record_type:
            requested_type = str(record_type).lower().strip()
            records = [
                r for r in records
                if str(r.get("type") or "unknown").lower() == requested_type
            ]

        if not normalized or not records:
            return {
                "matched": False,
                "ambiguous": False,
                "query": query,
                "service": service_name,
                "suggestions": [],
                "search_strategies": [],
            }

        exact_index: Dict[str, set] = {}
        token_index: Dict[str, set] = {}
        prefix_index: Dict[str, set] = {}
        gram_index: Dict[str, set] = {}
        record_terms: Dict[int, List[str]] = {}

        def add_index(index: Dict[str, set], key: str, idx: int) -> None:
            if key:
                index.setdefault(key, set()).add(idx)

        for idx, record in enumerate(records):
            raw_terms = [
                record.get("name") or "",
                record.get("display_name") or "",
                *(record.get("aliases") or []),
                record.get("jid") or "",
                record.get("chat_id") or "",
            ]
            phone = self._normalize_phone(record.get("phone") or "")
            if phone:
                raw_terms.append(phone)

            terms = []
            seen_terms = set()
            for raw_term in raw_terms:
                term = self._normalize_search_text(raw_term)
                if not term or term in seen_terms:
                    continue
                seen_terms.add(term)
                terms.append(term)
                add_index(exact_index, term, idx)

                for token in self._tokens(term):
                    add_index(token_index, token, idx)
                    for length in range(2, min(len(token), 14) + 1):
                        add_index(prefix_index, token[:length], idx)

                for gram in self._ngrams(term):
                    add_index(gram_index, gram, idx)

            record_terms[idx] = terms

        strategies_used = []
        candidate_ids = set()

        if normalized in exact_index:
            candidate_ids.update(exact_index[normalized])
            strategies_used.append("exact_hash")

        if phone_query:
            phone_key = self._normalize_search_text(phone_query)
            if phone_key in exact_index:
                candidate_ids.update(exact_index[phone_key])
                strategies_used.append("phone_hash")

        if query_tokens:
            token_sets = [token_index.get(token, set()) for token in query_tokens]
            if token_sets and all(token_sets):
                intersection = set.intersection(*token_sets)
                if intersection:
                    candidate_ids.update(intersection)
                    strategies_used.append("token_inverted_index")
            for token in query_tokens:
                pref = prefix_index.get(token, set())
                if pref:
                    candidate_ids.update(pref)
                    if "prefix_index" not in strategies_used:
                        strategies_used.append("prefix_index")

        if query_grams:
            gram_hits: Dict[int, int] = {}
            for gram in query_grams:
                for idx in gram_index.get(gram, set()):
                    gram_hits[idx] = gram_hits.get(idx, 0) + 1
            if gram_hits:
                max_hits = max(gram_hits.values())
                cutoff = max(1, int(max_hits * 0.45))
                candidate_ids.update(idx for idx, hits in gram_hits.items() if hits >= cutoff)
                strategies_used.append("trigram_inverted_index")

        for idx, terms in record_terms.items():
            if any(normalized in term or term in normalized for term in terms):
                candidate_ids.add(idx)
                if "substring_scan" not in strategies_used:
                    strategies_used.append("substring_scan")

        if not candidate_ids:
            candidate_ids = set(range(len(records)))
            strategies_used.append("full_fuzzy_scan")

        ranked = []
        for idx in candidate_ids:
            record = records[idx]
            best = 0.0
            best_strategy = "hybrid_fuzzy"

            for term in record_terms.get(idx, []):
                if term == normalized:
                    score = 1.0
                    strategy = "exact"
                else:
                    term_tokens = set(term.split())
                    token_overlap = (
                        len(query_tokens & term_tokens) / max(1, len(query_tokens | term_tokens))
                        if query_tokens or term_tokens else 0.0
                    )
                    token_fuzzy_parts = []
                    for query_token in query_tokens:
                        best_token_score = 0.0
                        for term_token in term_tokens:
                            token_seq = SequenceMatcher(None, query_token, term_token).ratio()
                            token_distance = self._levenshtein_distance(query_token, term_token)
                            token_edit = 1.0 - (
                                token_distance / max(1, len(query_token), len(term_token))
                            )
                            best_token_score = max(
                                best_token_score,
                                (0.55 * token_seq) + (0.45 * token_edit),
                            )
                        token_fuzzy_parts.append(best_token_score)
                    token_fuzzy = (
                        sum(token_fuzzy_parts) / len(token_fuzzy_parts)
                        if token_fuzzy_parts else 0.0
                    )
                    prefix = 1.0 if (
                        len(normalized) >= 2 and (
                            term.startswith(normalized) or normalized.startswith(term)
                        )
                    ) else 0.0
                    substring = 1.0 if (
                        len(normalized) >= 3 and (normalized in term or term in normalized)
                    ) else 0.0
                    seq = SequenceMatcher(None, normalized, term).ratio()
                    distance = self._levenshtein_distance(normalized, term)
                    edit = 1.0 - (distance / max(1, len(normalized), len(term)))
                    term_grams = self._ngrams(term)
                    gram = (
                        len(query_grams & term_grams) / max(1, len(query_grams | term_grams))
                        if query_grams or term_grams else 0.0
                    )
                    score = max(
                        0.97 * prefix,
                        0.95 * substring,
                        0.94 * token_overlap,
                        0.93 * token_fuzzy,
                        (0.36 * seq) + (0.30 * edit) + (0.14 * gram) + (0.10 * token_overlap) + (0.10 * token_fuzzy),
                    )
                    strategy = "hybrid_fuzzy"

                if score > best:
                    best = score
                    best_strategy = strategy

            record_phone = self._normalize_phone(record.get("phone") or "")
            if phone_query and record_phone:
                if record_phone == phone_query:
                    best = max(best, 1.0)
                    best_strategy = "phone_exact"
                elif len(phone_query) >= 7 and record_phone.endswith(phone_query):
                    best = max(best, 0.97)
                    best_strategy = "phone_suffix"

            if best >= 0.52:
                ranked.append((best, best_strategy, record))

        ranked.sort(
            key=lambda item: (
                item[0],
                float(item[2].get("last_seen", 0) or 0),
            ),
            reverse=True,
        )

        def compact(record: Dict[str, Any], score: float, strategy: str) -> Dict[str, Any]:
            return {
                "name": record.get("name"),
                "type": record.get("type"),
                "phone": record.get("phone"),
                "jid": record.get("jid"),
                "score": round(score, 3),
                "strategy": strategy,
            }

        if not ranked:
            return {
                "matched": False,
                "ambiguous": False,
                "query": query,
                "service": service_name,
                "suggestions": [],
                "search_strategies": strategies_used,
            }

        top_score, top_strategy, top = ranked[0]
        second_score = ranked[1][0] if len(ranked) > 1 else 0.0
        margin = top_score - second_score
        confident = (
            top_score >= 0.985
            or (top_score >= 0.90 and margin >= 0.035)
            or (top_score >= 0.82 and margin >= 0.10)
        )

        if confident:
            return {
                "matched": True,
                "ambiguous": False,
                "query": query,
                "service": service_name,
                "name": top.get("name"),
                "record": top,
                "resolution": f"multi_search:{top_strategy}",
                "score": round(top_score, 3),
                "search_strategies": strategies_used,
                "runner_up_score": round(second_score, 3) if len(ranked) > 1 else None,
            }

        return {
            "matched": False,
            "ambiguous": True,
            "query": query,
            "service": service_name,
            "suggestions": [
                compact(record, score, strategy)
                for score, strategy, record in ranked[:10]
            ],
            "search_strategies": strategies_used,
        }

    def heartbeat(self) -> None:
        with self._lock:
            self._last_extension_seen = time.time()

    def update_browser_context(self, context: Dict[str, Any]) -> None:
        with self._lock:
            self._last_extension_seen = time.time()
            self._browser_context = {
                "title": str(context.get("title", ""))[:500],
                "url": str(context.get("url", ""))[:2000],
                "window_id": context.get("window_id"),
                "tab_id": context.get("tab_id"),
                "tab_count": context.get("tab_count"),
                "extension_version": str(context.get("extension_version", ""))[:50],
                "updated_at": time.time(),
            }

    def get_browser_context(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._browser_context)

    def submit_browser_action(self, action: Dict[str, Any], timeout: float = 8.0) -> Dict[str, Any]:
        """Queue a privileged Chrome-extension background action such as focusing a service tab."""
        action_id = uuid.uuid4().hex
        payload = dict(action)
        payload["action_id"] = action_id
        payload["created_at"] = time.time()
        event = threading.Event()

        with self._lock:
            self._browser_action_payloads[action_id] = payload
            self._browser_action_events[action_id] = event
            self._browser_actions.append(action_id)

        if not event.wait(timeout=max(1.0, timeout)):
            with self._lock:
                self._browser_action_payloads.pop(action_id, None)
                self._browser_action_events.pop(action_id, None)
                try:
                    self._browser_actions.remove(action_id)
                except ValueError:
                    pass
            return {
                "success": False,
                "verified": False,
                "action_id": action_id,
                "error": "MAYA Browser Bridge did not respond to the browser action in time.",
            }

        with self._lock:
            result = dict(self._browser_action_results.pop(action_id, {}))
            self._browser_action_events.pop(action_id, None)
            self._browser_action_payloads.pop(action_id, None)
        result.setdefault("action_id", action_id)
        return result

    def next_browser_action(self) -> Optional[Dict[str, Any]]:
        self.heartbeat()
        with self._lock:
            while self._browser_actions:
                action_id = self._browser_actions.popleft()
                payload = self._browser_action_payloads.get(action_id)
                if payload:
                    return dict(payload)
        return None

    def complete_browser_action(self, action_id: str, result: Dict[str, Any]) -> bool:
        with self._lock:
            event = self._browser_action_events.get(action_id)
            if not event:
                return False
            self._browser_action_results[action_id] = dict(result)
            event.set()
            return True

    def submit(self, command: Dict[str, Any], timeout: float = 25.0) -> Dict[str, Any]:
        service = str(command.get("service", "")).lower().strip()
        if service not in self._queues:
            return {"success": False, "verified": False, "error": f"Unsupported communication service: {service}"}

        command_id = uuid.uuid4().hex
        payload = dict(command)
        payload["command_id"] = command_id
        payload["created_at"] = time.time()
        payload["status"] = "queued"

        event = threading.Event()
        with self._lock:
            self._commands[command_id] = payload
            self._events[command_id] = event
            self._queues[service].append(command_id)

        if not event.wait(timeout=max(1.0, timeout)):
            with self._lock:
                existing = self._commands.get(command_id)
                if existing:
                    existing["status"] = "timed_out"
            return {
                "success": False,
                "verified": False,
                "command_id": command_id,
                "error": (
                    "MAYA Chrome Bridge did not respond in time. "
                    "Make sure Chrome is open on the requested profile and the MAYA Browser Bridge extension is enabled."
                ),
            }

        with self._lock:
            result = dict(self._results.pop(command_id, {}))
            self._events.pop(command_id, None)
        result.setdefault("command_id", command_id)
        return result

    def next_command(self, service: str, tab_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
        service = service.lower().strip()
        if service not in self._queues:
            return None

        self.heartbeat()
        with self._lock:
            queue = self._queues[service]
            attempts = len(queue)
            for _ in range(attempts):
                command_id = queue.popleft()
                command = self._commands.get(command_id)
                if not command or command.get("status") != "queued":
                    continue

                target_tab_id = command.get("target_tab_id")
                if target_tab_id is not None and int(target_tab_id) != int(tab_id or -1):
                    # This command was explicitly bound to the Chrome tab that
                    # was active when the user said "current chat".
                    queue.append(command_id)
                    continue

                command["status"] = "dispatched"
                command["dispatched_at"] = time.time()

                # Never reveal an arbitrary local filesystem path to page content.
                public_command = dict(command)
                attachment_path = public_command.pop("attachment_path", None)
                public_command.pop("target_tab_id", None)
                if attachment_path:
                    public_command["has_attachment"] = True
                    public_command["attachment_name"] = os.path.basename(attachment_path)
                    public_command["attachment_size"] = os.path.getsize(attachment_path)
                    public_command["attachment_mime"] = (
                        mimetypes.guess_type(attachment_path)[0]
                        or "application/octet-stream"
                    )
                else:
                    public_command["has_attachment"] = False
                return public_command
        return None

    def get_attachment(self, command_id: str) -> Optional[Dict[str, Any]]:
        """Return the attachment bound to an exact dispatched communication command."""
        with self._lock:
            command = self._commands.get(command_id)
            if not command or command.get("status") != "dispatched":
                return None
            path = command.get("attachment_path")
            if not path or not os.path.isfile(path):
                return None
            return {
                "path": path,
                "name": os.path.basename(path),
                "mime_type": mimetypes.guess_type(path)[0] or "application/octet-stream",
                "size_bytes": os.path.getsize(path),
            }

    def complete(self, command_id: str, result: Dict[str, Any]) -> bool:
        with self._lock:
            command = self._commands.get(command_id)
            event = self._events.get(command_id)
            if not command or not event:
                return False
            command["status"] = "completed"
            command["completed_at"] = time.time()
            self._results[command_id] = dict(result)
            event.set()
            return True

    def status(self) -> Dict[str, Any]:
        with self._lock:
            pending = sum(
                1 for command in self._commands.values()
                if command.get("status") in {"queued", "dispatched"}
            )
            last_seen = self._last_extension_seen
        return {
            "connected_recently": bool(last_seen and (time.time() - last_seen) < 5.0),
            "last_extension_seen": last_seen,
            "pending_commands": pending,
            "browser_context": self.get_browser_context(),
            "contact_counts": {
                service: len(values)
                for service, values in self._contacts.items()
            },
        }


communication_bridge = CommunicationBridge()
