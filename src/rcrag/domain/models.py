from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class Evidence:
    """Represents a piece of evidence used to support a record."""
    source_id: str
    weight: float = 1.0
    description: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API serialization."""
        return {
            'source_id': self.source_id,
            'weight': self.weight,
            'description': self.description
        }


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
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API serialization."""
        return {
            'id': self.id,
            'kind': self.kind,
            'content': self.content,
            'provenance_ids': self.provenance_ids,
            'evidence': [e.to_dict() for e in self.evidence],
            'metadata': self.metadata or {},
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
