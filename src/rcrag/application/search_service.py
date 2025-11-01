import math
import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Protocol, Sequence, Tuple


@dataclass
class SearchResult:
    record: Any
    score: float


class SearchPort(Protocol):
    def search(self, query: str, filters: Optional[Dict[str, Any]] = None) -> List[SearchResult]:
        ...


class HistorianLike(Protocol):
    def list_records(self, limit: Optional[int] = None) -> Sequence[Any]:
        ...


class BasicSearchService(SearchPort):
    """
    Basic hybrid search:
    - Term filtering over historian records
    - Keyword matching on subject/summary/body
    - Merges and ranks by simple BM25-like heuristic (very simplified)
    - Stub for embedding-based search (Phase 3)
    """

    def __init__(self, historian: HistorianLike) -> None:
        self.historian = historian

    def search(self, query: str, filters: Optional[Dict[str, Any]] = None) -> List[SearchResult]:
        # Fetch corpus
        try:
            records = list(self.historian.list_records())  # type: ignore[arg-type]
        except TypeError:
            # If list_records requires args
            records = list(self.historian.list_records(None))  # type: ignore

        # Filter by simple terms in metadata if provided
        if filters:
            def record_matches_filters(r: Any) -> bool:
                meta = getattr(r, "metadata", None) or getattr(r, "terms", None) or {}
                if isinstance(meta, dict):
                    for k, v in filters.items():
                        if meta.get(k) != v:
                            return False
                    return True
                return True
            records = [r for r in records if record_matches_filters(r)]

        # Tokenize query
        tokens = [t.lower() for t in re.findall(r"\w+", query)]
        if not tokens:
            return []

        # Score records
        results: List[SearchResult] = []
        for r in records:
            text = " ".join([
                str(getattr(r, "subject", "") or ""),
                str(getattr(r, "summary", "") or ""),
                str(getattr(r, "body", "") or ""),
            ]).lower()
            if not text.strip():
                continue

            tf = 0
            for t in tokens:
                tf += text.count(t)
            if tf == 0:
                continue

            # Very rough weighting by field presence
            score = tf / math.sqrt(len(text) + 1.0)
            results.append(SearchResult(record=r, score=score))

        # Sort desc by score
        results.sort(key=lambda x: x.score, reverse=True)
        return results

    # Placeholder for future embedding-based search
    def search_with_embeddings(self, query: str, top_k: int = 10) -> List[SearchResult]:
        return []
