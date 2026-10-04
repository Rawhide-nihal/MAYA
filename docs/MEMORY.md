# MAYA Persistent Memory Architecture

MAYA implements a persistent multi-tier memory system backed by SQLite and TF-IDF vector similarity.

## Memory Categories

1. **Short-Term Conversational Context**:
   - Immediate conversation buffer and active session turns.
2. **Episodic Memory**:
   - Records discrete historical events and past user interactions (e.g. *"User debugged Minecraft bridge yesterday"*).
3. **Semantic Memory**:
   - Stable facts and learned knowledge about the user, preferred editors, response style, and operating system.
4. **Project Memory**:
   - Tracks project names, local paths, primary languages, build systems, Git branches, and known errors.
5. **Action Memory**:
   - Detailed ledger of executed tools and operations.

## Memory Extraction Pipeline
When the user speaks with MAYA, messages pass through the extraction pipeline:
```
User Message
    │
    ▼
Candidate Fact Extraction (regex & heuristics)
    │
    ▼
Importance Scoring (1.0 to 5.0)
    │
    ▼
Deduplication & Storage (INSERT OR REPLACE in SQLite)
    │
    ▼
Semantic Retrieval (TF-IDF Cosine Similarity)
```

Only top relevant memories are injected into conversational prompts to preserve inference efficiency.
