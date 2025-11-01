from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class HistorianRecordSchema(BaseModel):
    id: str = Field(..., description="Record ID")
    subject: Optional[str] = None
    summary: Optional[str] = None
    body: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    @classmethod
    def from_domain(cls, record: Any) -> "HistorianRecordSchema":
        # Domain may be dataclass or dict
        if isinstance(record, dict):
            return cls(
                id=str(record.get("id")),
                subject=record.get("subject"),
                summary=record.get("summary"),
                body=record.get("body"),
                metadata=record.get("metadata") or record.get("terms"),
            )
        return cls(
            id=str(getattr(record, "id")),
            subject=getattr(record, "subject", None),
            summary=getattr(record, "summary", None),
            body=getattr(record, "body", None),
            metadata=getattr(record, "metadata", None) or getattr(record, "terms", None),
        )

    def to_domain(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "subject": self.subject,
            "summary": self.summary,
            "body": self.body,
            "metadata": self.metadata,
        }


class QueryRequest(BaseModel):
    query: str = Field(..., description="Query text")
    filters: Optional[Dict[str, Any]] = Field(default=None, description="Optional filter terms")


class QueryResponse(BaseModel):
    query: str
    results: List[HistorianRecordSchema]
    scores: Optional[Dict[str, float]] = Field(default=None, description="Optional trust scores")
