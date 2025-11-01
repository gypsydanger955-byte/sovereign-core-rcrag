from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
import uuid


@dataclass(frozen=True)
class Evidence:
    """
    Represents a piece of evidence linked to a HistorianRecord.
    """
    id: str
    type: str  # url|s3_path|ipfs_hash|internal_log_id|local_file
    ref: str
    hash: str  # SHA-256 hash of the evidence content at ingestion time
    signature: Optional[str] = None  # Optional cryptographic signature
    timestamp_captured: str = ""  # RFC3339 timestamp when evidence was captured


@dataclass(frozen=True)
class HistorianRecord:
    """
    Immutable record representing an event or piece of knowledge in the Historian.
    """
    id: str
    timestamp: str  # RFC3339
    actor_id: str
    actor_type: str  # hub|manus|human|external
    kind: str  # proposal|execution_report|fact|artifact|verification_event|dispute_event|superseded_version|metadata_update
    subject: str
    summary: str
    body_md: str
    provenance_ids: List[str] = field(default_factory=list)
    status: str = "pending"  # pending|active|superseded|disputed|rejected|revoked
    evidence: List[Evidence] = field(default_factory=list)
    verification_event_ids: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        # Validate UUID format for id and provenance_ids
        try:
            uuid.UUID(self.id)
        except Exception as e:
            raise ValueError(f"Invalid UUID for id: {self.id}") from e
        for pid in self.provenance_ids:
            try:
                uuid.UUID(pid)
            except Exception as e:
                raise ValueError(f"Invalid UUID in provenance_ids: {pid}") from e
        for evid in self.evidence:
            try:
                uuid.UUID(evid.id)
            except Exception as e:
                raise ValueError(f"Invalid UUID in evidence id: {evid.id}") from e
        for veid in self.verification_event_ids:
            try:
                uuid.UUID(veid)
            except Exception as e:
                raise ValueError(f"Invalid UUID in verification_event_ids: {veid}") from e
