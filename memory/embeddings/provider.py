"""
MAYA Vector Embedding & Semantic Memory Provider
Computes vector representations and cosine similarity rankings over memories,
with preference supersession and temporal recency decay.
"""
import math
import time
from typing import List, Dict, Any, Optional, Tuple
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

class MemoryEmbeddingProvider:
    def __init__(self, min_similarity_threshold: float = 0.12):
        self.min_similarity_threshold = min_similarity_threshold
        self.vectorizer = TfidfVectorizer(ngram_range=(1, 2), stop_words="english")

    def rank_memories(
        self,
        query: str,
        memories: List[Dict[str, Any]],
        top_k: int = 5
    ) -> List[Tuple[Dict[str, Any], float]]:
        """
        Ranks memories against a user query using vector cosine similarity,
        factoring in importance weights and temporal recency decay.
        """
        if not memories or not query.strip():
            return []

        # Filter out superseded memories
        active = [m for m in memories if not m.get("superseded", 0)]
        if not active:
            return []

        texts = []
        for m in active:
            cat = m.get("category", "")
            key = m.get("key", "")
            content = m.get("content", "")
            texts.append(f"{cat} {key}: {content}" if cat or key else content)

        try:
            tfidf_mat = self.vectorizer.fit_transform(texts + [query])
            doc_vecs = tfidf_mat[:-1]
            query_vec = tfidf_mat[-1]

            sims = cosine_similarity(query_vec, doc_vecs).flatten()

            scored = []
            now = time.time()
            for idx, sim in enumerate(sims):
                if sim < self.min_similarity_threshold:
                    continue
                mem = active[idx]
                importance = float(mem.get("importance", 1.0))
                age_days = (now - float(mem.get("timestamp", now))) / 86400.0
                recency_decay = math.exp(-0.01 * min(age_days, 30.0))

                final_score = float(sim * (1.0 + 0.15 * importance) * recency_decay)
                scored.append((mem, round(final_score, 4)))

            scored.sort(key=lambda x: x[1], reverse=True)
            return scored[:top_k]
        except Exception:
            # Fallback keyword match
            q_low = query.lower()
            results = []
            for m in active:
                c = m.get("content", "").lower()
                if any(w in c for w in q_low.split() if len(w) > 3):
                    results.append((m, 0.5))
            return results[:top_k]
