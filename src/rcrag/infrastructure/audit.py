import json
import logging
from typing import Any, Dict, Iterable, Optional

from src.rcrag.infrastructure.logging import get_correlation_id


class AuditLogger:
    """
    Emits structured audit events for queries.
    """

    def __init__(self, logger: Optional[logging.Logger] = None, policy_version: str = "v1") -> None:
        self.logger = logger or logging.getLogger("audit")
        self.policy_version = policy_version

    def log_query(
        self,
        *,
        query: str,
        selected_records: Iterable[Any],
        trust_scores: Optional[Dict[str, float]] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        corr_id = get_correlation_id()
        record_ids = []
        for r in selected_records or []:
            rid = getattr(r, "id", None)
            if rid is None and isinstance(r, dict):
                rid = r.get("id")
            record_ids.append(rid)
        payload: Dict[str, Any] = {
            "event": "query",
            "policy_version": self.policy_version,
            "correlation_id": corr_id,
            "query": query,
            "selected_record_ids": record_ids,
        }
        if trust_scores is not None:
            payload["trust_scores"] = trust_scores
        if extra:
            payload.update(extra)
        # Use logger to emit as JSON if configured, else as text
        try:
            self.logger.info(json.dumps(payload))
        except Exception:
            # Fallback: log dict
            self.logger.info(payload)
