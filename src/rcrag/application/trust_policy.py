from typing import Iterable, List, Optional, Tuple

from ..domain.models import HistorianRecord


class TrustPolicy:
    """Computes trust scores and filters context based on a threshold."""

    def __init__(self, threshold: float = 0.85):
        self.threshold = threshold

    def compute_trust_score(self, record: HistorianRecord) -> float:
        # Evidence-driven score with provenance bonus
        if record.evidence:
            weights = [max(0.0, min(1.0, ev.weight)) for ev in record.evidence]
            avg = sum(weights) / len(weights)
        else:
            avg = 0.5
        provenance_bonus = min(0.2, 0.05 * len(record.provenance_ids or []))
        score = min(1.0, max(0.0, 0.2 + 0.8 * avg + provenance_bonus))
        return score

    def filter_context(self, records: Iterable[HistorianRecord], threshold: Optional=float) -> List[HistorianRecord]:
        cut = self.threshold if threshold is None else threshold
        scored: List[Tuple[HistorianRecord, float]] = [(r, self.compute_trust_score(r)) for r in records]
        filtered = [r for r, s in scored if s >= cut]
        filtered.sort(key=lambda r: self.compute_trust_score(r), reverse=True)
        return filtered
