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
