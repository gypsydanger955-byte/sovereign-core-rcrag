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
