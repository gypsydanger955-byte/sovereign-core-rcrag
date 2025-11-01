```filename: src/historian/models.py
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
```

```filename: src/historian/historian_client.py
from abc import ABC, abstractmethod
from typing import Optional, List
from src.historian.models import HistorianRecord


class HistorianClient(ABC):
    """
    Abstract base class for Historian clients.
    """

    @abstractmethod
    async def create_record(self, record: HistorianRecord) -> str:
        """
        Create a new immutable record. Returns the record ID.
        """
        raise NotImplementedError()

    @abstractmethod
    async def get_record(self, record_id: str) -> Optional[HistorianRecord]:
        """
        Retrieve a record by ID.
        """
        raise NotImplementedError()

    @abstractmethod
    async def query_by_kind(self, kind: str, limit: int = 10) -> List[HistorianRecord]:
        """
        Query records by kind.
        """
        raise NotImplementedError()

    @abstractmethod
    async def query_by_provenance(self, source_id: str) -> List[HistorianRecord]:
        """
        Find all records that reference a source_id in provenance_ids.
        """
        raise NotImplementedError()
```

```filename: src/historian/inmemory_historian_client.py
import asyncio
from typing import Optional, List, Dict, Any
from src.historian.historian_client import HistorianClient
from src.historian.models import HistorianRecord, Evidence
import uuid
from datetime import datetime, timezone


class InMemoryHistorianClient(HistorianClient):
    """
    In-memory implementation for testing and development.
    """

    def __init__(self):
        self._records: Dict[str, HistorianRecord] = {}
        self._lock = asyncio.Lock()
        # Seed with some sample records for testing
        asyncio.get_event_loop().run_until_complete(self._seed_sample_records())

    async def _seed_sample_records(self):
        # Create a proposal record
        proposal_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        proposal = HistorianRecord(
            id=proposal_id,
            timestamp=now,
            actor_id="human-123",
            actor_type="human",
            kind="proposal",
            subject="test-proposal",
            summary="Test proposal for sample",
            body_md="This is a test proposal.",
            provenance_ids=[],
            status="pending",
            evidence=[],
            verification_event_ids=[],
            tags=["test"],
            metadata={}
        )
        await self.create_record(proposal)

    async def create_record(self, record: HistorianRecord) -> str:
        """
        Create a new immutable record. Enforce lifecycle validation.
        """
        async with self._lock:
            if record.id in self._records:
                raise ValueError(f"Record with id {record.id} already exists (immutable).")

            self.validate_record(record)

            self._records[record.id] = record
            return record.id

    async def get_record(self, record_id: str) -> Optional[HistorianRecord]:
        async with self._lock:
            return self._records.get(record_id)

    async def query_by_kind(self, kind: str, limit: int = 10) -> List[HistorianRecord]:
        async with self._lock:
            results = [r for r in self._records.values() if r.kind == kind]
            return results[:limit]

    async def query_by_provenance(self, source_id: str) -> List[HistorianRecord]:
        async with self._lock:
            results = [r for r in self._records.values() if source_id in r.provenance_ids]
            return results

    def validate_record(self, record: HistorianRecord) -> None:
        """
        Validate record before creation.
        Enforce lifecycle: proposal -> execution_report -> fact
        Also validate verification_event has target_record_id in metadata.
        """
        kind = record.kind
        provenance_ids = record.provenance_ids

        # Check provenance requirements based on kind
        if kind == "execution_report":
            # Must have exactly one proposal in provenance_ids
            if not provenance_ids:
                raise ValueError("execution_report must have at least one provenance_id referencing a proposal.")
            # Check that all provenance_ids exist and at least one is a proposal
            proposals = []
            for pid in provenance_ids:
                p = self._records.get(pid)
                if p is None:
                    raise ValueError(f"Provenance record {pid} does not exist.")
                if p.kind == "proposal":
                    proposals.append(p)
            if not proposals:
                raise ValueError("execution_report must have at least one proposal in provenance_ids.")

        elif kind == "fact":
            # Must have at least one execution_report in provenance_ids
            if not provenance_ids:
                raise ValueError("fact must have at least one provenance_id referencing an execution_report.")
            execution_reports = []
            for pid in provenance_ids:
                p = self._records.get(pid)
                if p is None:
                    raise ValueError(f"Provenance record {pid} does not exist.")
                if p.kind == "execution_report":
                    execution_reports.append(p)
            if not execution_reports:
                raise ValueError("fact must have at least one execution_report in provenance_ids.")

        elif kind == "verification_event":
            # Must have target_record_id in metadata
            target_id = record.metadata.get("target_record_id")
            if not target_id:
                raise ValueError("verification_event must have 'target_record_id' in metadata.")
            # Target record must exist
            if target_id not in self._records:
                raise ValueError(f"verification_event target_record_id {target_id} does not exist.")

        # For other kinds, no special validation for now

    async def create_verification_event(
        self,
        target_record_id: str,
        actor_id: str,
        method: str,
        status: str,  # accepted|rejected|inconclusive
        notes: str
    ) -> str:
        """
        Create a verification event and update target record status.
        """
        async with self._lock:
            if target_record_id not in self._records:
                raise ValueError(f"Target record {target_record_id} does not exist.")

            now = datetime.now(timezone.utc).isoformat()
            ve_id = str(uuid.uuid4())
            ve = HistorianRecord(
                id=ve_id,
                timestamp=now,
                actor_id=actor_id,
                actor_type="human",  # Assuming human for simplicity; could be param
                kind="verification_event",
                subject=f"Verification of {target_record_id}",
                summary=f"Verification event with status {status}",
                body_md=notes,
                provenance_ids=[target_record_id],
                status="active",
                evidence=[],
                verification_event_ids=[],
                tags=[method],
                metadata={"target_record_id": target_record_id, "verification_status": status, "method": method, "notes": notes}
            )
            # Validate verification event
            self.validate_record(ve)

            # Store verification event
            self._records[ve_id] = ve

            # Update target record's verification_event_ids and status if accepted
            target_record = self._records[target_record_id]
            updated_verification_ids = target_record.verification_event_ids + [ve_id]
            updated_status = target_record.status
            if status == "accepted":
                updated_status = "active"

            # Since records are immutable, create a new HistorianRecord with updated fields
            updated_record = HistorianRecord(
                id=target_record.id,
                timestamp=target_record.timestamp,
                actor_id=target_record.actor_id,
                actor_type=target_record.actor_type,
                kind=target_record.kind,
                subject=target_record.subject,
                summary=target_record.summary,
                body_md=target_record.body_md,
                provenance_ids=target_record.provenance_ids,
                status=updated_status,
                evidence=target_record.evidence,
                verification_event_ids=updated_verification_ids,
                tags=target_record.tags,
                metadata=target_record.metadata,
            )
            # Replace old record with updated one (immutability here means no update, but for in-memory we replace)
            self._records[target_record_id] = updated_record

            return ve_id
```

```filename: src/main.py
import uvicorn
from fastapi import FastAPI, Query, HTTPException
from typing import List, Optional
from src.historian.inmemory_historian_client import InMemoryHistorianClient
from src.historian.models import HistorianRecord
import asyncio

app = FastAPI(title="RCRAG API")

historian_client = InMemoryHistorianClient()


@app.get("/rcrag/query", response_model=List[HistorianRecord])
async def rcrag_query(
    verification_status: Optional[str] = Query(
        None,
        description="Filter facts by verification status: active, pending, disputed, rejected"
    ),
    limit: int = Query(10, ge=1, le=100)
):
    """
    Query the Historian for kind='fact' records with optional verification status filter.
    Returns full records.
    """
    # Query facts
    facts = await historian_client.query_by_kind("fact", limit=1000)  # get more to filter

    # Filter by status if specified
    if verification_status:
        facts = [f for f in facts if f.status == verification_status]

    # Limit results
    facts = facts[:limit]

    # Optionally, could add provenance chain here - omitted for brevity

    return facts


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

```filename: tests/test_historian.py
import pytest
import asyncio
from src.historian.inmemory_historian_client import InMemoryHistorianClient
from src.historian.models import HistorianRecord, Evidence
import uuid
from datetime import datetime, timezone


@pytest.mark.asyncio
async def test_create_proposal_and_execution_report_and_fact():
    client = InMemoryHistorianClient()

    # Create a proposal
    proposal_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    proposal = HistorianRecord(
        id=proposal_id,
        timestamp=now,
        actor_id="human-1",
        actor_type="human",
        kind="proposal",
        subject="test-subject",
        summary="Test proposal",
        body_md="Proposal body",
        provenance_ids=[],
        status="pending",
        evidence=[],
        verification_event_ids=[],
        tags=[],
        metadata={}
    )
    await client.create_record(proposal)

    # Create execution_report referencing proposal
    exec_id = str(uuid.uuid4())
    execution_report = HistorianRecord(
        id=exec_id,
        timestamp=now,
        actor_id="manus-1",
        actor_type="manus",
        kind="execution_report",
        subject="test-subject",
        summary="Execution report",
        body_md="Execution details",
        provenance_ids=[proposal_id],
        status="pending",
        evidence=[],
        verification_event_ids=[],
        tags=[],
        metadata={}
    )
    await client.create_record(execution_report)

    # Create fact referencing execution_report
    fact_id = str(uuid.uuid4())
    fact = HistorianRecord(
        id=fact_id,
        timestamp=now,
        actor_id="manus-1",
        actor_type="manus",
        kind="fact",
        subject="test-subject",
        summary="Fact summary",
        body_md="Fact details",
        provenance_ids=[exec_id],
        status="pending",
        evidence=[],
        verification_event_ids=[],
        tags=[],
        metadata={}
    )
    await client.create_record(fact)

    # Try creating execution_report without proposal - should fail
    bad_exec = HistorianRecord(
        id=str(uuid.uuid4()),
        timestamp=now,
        actor_id="manus-1",
        actor_type="manus",
        kind="execution_report",
        subject="test-subject",
        summary="Bad exec",
        body_md="No proposal",
        provenance_ids=[],
        status="pending",
        evidence=[],
        verification_event_ids=[],
        tags=[],
        metadata={}
    )
    with pytest.raises(ValueError):
        await client.create_record(bad_exec)

    # Try creating fact without execution_report - should fail
    bad_fact = HistorianRecord(
        id=str(uuid.uuid4()),
        timestamp=now,
        actor_id="manus-1",
        actor_type="manus",
        kind="fact",
        subject="test-subject",
        summary="Bad fact",
        body_md="No exec report",
        provenance_ids=[],
        status="pending",
        evidence=[],
        verification_event_ids=[],
        tags=[],
        metadata={}
    )
    with pytest.raises(ValueError):
        await client.create_record(bad_fact)


@pytest.mark.asyncio
async def test_verification_event_creates_and_updates_status():
    client = InMemoryHistorianClient()

    # Create proposal
    proposal_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    proposal = HistorianRecord(
        id=proposal_id,
        timestamp=now,
        actor_id="human-1",
        actor_type="human",
        kind="proposal",
        subject="verify-test",
        summary="Proposal for verification test",
        body_md="Proposal body",
        provenance_ids=[],
        status="pending",
        evidence=[],
        verification_event_ids=[],
        tags=[],
        metadata={}
    )
    await client.create_record(proposal)

    # Create execution_report referencing proposal
    exec_id = str(uuid.uuid4())
    execution_report = HistorianRecord(
        id=exec_id,
        timestamp=now,
        actor_id="manus-1",
        actor_type="manus",
        kind="execution_report",
        subject="verify-test",
        summary="Execution report",
        body_md="Execution details",
        provenance_ids=[proposal_id],
        status="pending",
        evidence=[],
        verification_event_ids=[],
        tags=[],
        metadata={}
    )
    await client.create_record(execution_report)

    # Create fact referencing execution_report
    fact_id = str(uuid.uuid4())
    fact = HistorianRecord(
        id=fact_id,
        timestamp=now,
        actor_id="manus-1",
        actor_type="manus",
        kind="fact",
        subject="verify-test",
        summary="Fact summary",
        body_md="Fact details",
        provenance_ids=[exec_id],
        status="pending",
        evidence=[],
        verification_event_ids=[],
        tags=[],
        metadata={}
    )
    await client.create_record(fact)

    # Create verification event for fact with accepted status
    ve_id = await client.create_verification_event(
        target_record_id=fact_id,
        actor_id="human-2",
        method="manual_review",
        status="accepted",
        notes="Verified manually."
    )
    assert ve_id is not None

    # Retrieve fact and check status updated to active
    updated_fact = await client.get_record(fact_id)
    assert updated_fact is not None
    assert updated_fact.status == "active"
    assert ve_id in updated_fact.verification_event_ids

    # Create verification event with rejected status - should not update fact status to active
    ve_id2 = await client.create_verification_event(
        target_record_id=fact_id,
        actor_id="human-3",
        method="auto_check",
        status="rejected",
        notes="Auto check failed."
    )
    updated_fact2 = await client.get_record(fact_id)
    assert updated_fact2 is not None
    # Status remains active because accepted was set earlier
    assert updated_fact2.status == "active"
    assert ve_id2 in updated_fact2.verification_event_ids


@pytest.mark.asyncio
async def test_query_by_kind_and_provenance():
    client = InMemoryHistorianClient()

    # Create proposal
    proposal_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    proposal = HistorianRecord(
        id=proposal_id,
        timestamp=now,
        actor_id="human-1",
        actor_type="human",
        kind="proposal",
        subject="query-test",
        summary="Proposal for query test",
        body_md="Proposal body",
        provenance_ids=[],
        status="pending",
        evidence=[],
        verification_event_ids=[],
        tags=[],
        metadata={}
    )
    await client.create_record(proposal)

    # Create execution_report referencing proposal
    exec_id = str(uuid.uuid4())
    execution_report = HistorianRecord(
        id=exec_id,
        timestamp=now,
        actor_id="manus-1",
        actor_type="manus",
        kind="execution_report",
        subject="query-test",
        summary="Execution report",
        body_md="Execution details",
        provenance_ids=[proposal_id],
        status="pending",
        evidence=[],
        verification_event_ids=[],
        tags=[],
        metadata={}
    )
    await client.create_record(execution_report)

    # Query by kind 'proposal'
    proposals = await client.query_by_kind("proposal")
    assert any(p.id == proposal_id for p in proposals)

    # Query by provenance referencing proposal_id
    execs = await client.query_by_provenance(proposal_id)
    assert any(e.id == exec_id for e in execs)
```
