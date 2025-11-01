from typing import List, Tuple

from ..domain.models import HistorianRecord
from ..domain.ports.historian_port import HistorianPort
from .trust_policy import TrustPolicy


class RcragService:
    """Application service orchestrating historian queries and applying trust policy."""

    def __init__(self, historian: HistorianPort, trust_policy: TrustPolicy):
        self._historian = historian
        self._trust = trust_policy

    async def query(self, query: str, top_k: int = 3) -> List[HistorianRecord]:
        # Very simple heuristic to determine kind
        q = (query or "").lower()
        if q.startswith("kind:"):
            kind = q.split(":", 1)[1].strip() or "note"
        elif "source" in q:
            kind = "source"
        else:
            kind = "note"

        candidates = await self._historian.query_by_kind(kind, limit=max(10, top_k * 3))
        if not candidates:
            return []

        # Score all
        scored: List[Tuple[HistorianRecord, float]] = [(r, self._trust.compute_trust_score(r)) for r in candidates]
        # Filter by threshold
        above = [(r, s) for r, s in scored if s >= self._trust.threshold]
        # Choose best
        choose_from = above if above else scored
        choose_from.sort(key=lambda rs: rs[1], reverse=True)
        return [r for r, _ in choose_from[:top_k]]
