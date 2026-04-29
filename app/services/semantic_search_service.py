from __future__ import annotations

import math
import re
from collections import Counter

from app.models.memory_entry import MemoryEntry


TOKEN_RE = re.compile(r"[a-zA-Z0-9_+-]{2,}")
SYNONYMS = {
    "db": {"database", "postgres", "postgresql", "storage"},
    "database": {"db", "postgres", "postgresql", "storage"},
    "postgres": {"postgresql", "db", "database"},
    "postgresql": {"postgres", "db", "database"},
    "auth": {"authentication", "authorization", "token", "api-key"},
    "authentication": {"auth", "authorization", "token"},
    "search": {"retrieval", "find", "lookup", "query"},
    "memory": {"context", "knowledge", "state"},
    "import": {"ingest", "scan", "load"},
    "task": {"job", "work", "todo"},
}


class SemanticSearchService:
    @staticmethod
    def semantic_score(query: str, entry: MemoryEntry) -> float:
        query_tokens = SemanticSearchService._expanded_tokens(query)
        text_tokens = SemanticSearchService._expanded_tokens(f"{entry.title or ''} {entry.content}")
        if not query_tokens or not text_tokens:
            return 0.0

        query_counts = Counter(query_tokens)
        text_counts = Counter(text_tokens)
        shared_terms = set(query_counts).intersection(text_counts)
        dot = sum(query_counts[token] * text_counts[token] for token in shared_terms)
        query_norm = math.sqrt(sum(value * value for value in query_counts.values()))
        text_norm = math.sqrt(sum(value * value for value in text_counts.values()))
        if not query_norm or not text_norm:
            return 0.0

        cosine = dot / (query_norm * text_norm)
        coverage = len(shared_terms) / max(len(set(query_tokens)), 1)
        return min(1.0, cosine * 0.75 + coverage * 0.25)

    @staticmethod
    def _expanded_tokens(text: str) -> list[str]:
        base_tokens = [token.lower() for token in TOKEN_RE.findall(text)]
        expanded = list(base_tokens)
        for token in base_tokens:
            expanded.extend(sorted(SYNONYMS.get(token, set())))
        return expanded
