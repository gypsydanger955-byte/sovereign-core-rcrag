# Task for GPT-4: Implement Historian Data Model (Days 3-4)

## Context

Gemini (our strategic architect) has provided comprehensive guidance on the Historian data model. We're now implementing the prioritized features for Days 3-4.

**Strategic Guidance Summary:**
- **Multi-modal architecture**: Primary store + ChromaDB + Neo4j
- **Immutable, event-sourced model**: No updates, only new records
- **Provenance-first**: Every record links to its sources
- **Verification as events**: Separate `verification_event` records

## Your Mission: Implement Days 3-4 Priorities

### 1. Core Historian Record Schema

Implement the Historian record model with these fields:

```python
@dataclass
class HistorianRecord:
    id: str  # UUID
    timestamp: str  # RFC3339
    actor_id: str
    actor_type: str  # hub|manus|human|external
    kind: str  # proposal|execution_report|fact|artifact|verification_event
    subject: str
    summary: str
    body_md: str
    provenance_ids: List[str]  # Links to source records
    status: str  # pending|active|superseded|disputed|rejected
    evidence: List[Evidence]
    verification_event_ids: List[str]
    tags: List[str]
    metadata: Dict[str, Any]
```

### 2. Update `HistorianClient` Interface

Add these methods to the abstract `HistorianClient`:

```python
async def create_record(self, record: HistorianRecord) -> str:
    """Create a new immutable record. Returns the record ID."""
    
async def get_record(self, record_id: str) -> Optional[HistorianRecord]:
    """Retrieve a record by ID."""
    
async def query_by_kind(self, kind: str, limit: int = 10) -> List[HistorianRecord]:
    """Query records by kind."""
    
async def query_by_provenance(self, source_id: str) -> List[HistorianRecord]:
    """Find all records that reference a source_id in provenance_ids."""
```

### 3. Implement `InMemoryHistorianClient`

For Days 3-4, implement an in-memory version (we'll add ChromaDB/Neo4j in later phases):

```python
class InMemoryHistorianClient(HistorianClient):
    """In-memory implementation for testing and development."""
    
    def __init__(self):
        self._records: Dict[str, HistorianRecord] = {}
        # Add some sample records for testing
```

**Requirements:**
- Store records in a dictionary keyed by `id`
- Enforce immutability (no updates to existing records)
- Implement all abstract methods
- Add validation:
  - `execution_report` must have a `proposal` in `provenance_ids`
  - `fact` must have an `execution_report` in `provenance_ids`
  - `verification_event` must have a `target_record_id`

### 4. Lifecycle Logic

Implement validation logic to enforce the proposal → execution_report → fact lifecycle:

```python
def validate_record(self, record: HistorianRecord) -> None:
    """Validate record before creation."""
    # Check provenance requirements based on kind
    # Raise ValueError if validation fails
```

### 5. Basic Verification Logic

Implement simple verification status updates:

```python
async def create_verification_event(
    self, 
    target_record_id: str,
    actor_id: str,
    method: str,
    status: str,  # accepted|rejected|inconclusive
    notes: str
) -> str:
    """Create a verification event and update target record status."""
```

When a `verification_event` with `status: accepted` is created, update the target record's `status` to `active`.

### 6. Update RCRAG API

Modify `/rcrag/query` endpoint to:
- Query the Historian for `kind: fact` records with `status: active`
- Filter by verification status
- Return full provenance chain (optional)

## Files to Create/Modify

1. **CREATE**: `src/historian/models.py` - Data models (HistorianRecord, Evidence, etc.)
2. **MODIFY**: `src/historian/historian_client.py` - Add new abstract methods
3. **CREATE**: `src/historian/inmemory_historian_client.py` - In-memory implementation
4. **MODIFY**: `src/main.py` - Update to use new Historian methods
5. **CREATE**: `tests/test_historian.py` - Basic unit tests

## Success Criteria

- ✅ Can create immutable Historian records
- ✅ Lifecycle validation works (proposal → execution_report → fact)
- ✅ Verification events update record status
- ✅ RCRAG API returns only verified facts
- ✅ Provenance queries work
- ✅ All tests pass

## Technical Requirements

- Use Python dataclasses for models
- Use UUID for `id` generation
- Use ISO 8601 / RFC3339 for timestamps
- Include comprehensive docstrings
- Add type hints throughout
- Write clean, testable code

Please implement this now. Provide complete code for all files.
