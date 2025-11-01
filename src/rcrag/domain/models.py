from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class Evidence:
    """Represents a piece of evidence used to support a record."""
    source_id: str
    weight: float = 1.0
    description: Optional[str] = None


@dataclass
class HistorianRecord:
    """Immutable record stored in the Historian."""
    id: Optional[str] = None
    kind: str = "generic"
    content: str = ""
    provenance_ids: List[str] = field(default_factory=list)
    evidence: List[Evidence] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
