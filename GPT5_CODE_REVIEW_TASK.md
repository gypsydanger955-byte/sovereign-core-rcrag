# Task for GPT-5: Review Existing RCRAG Code and Create Refactoring Plan

## Context

You (GPT-5) just provided strategic guidance for architecting the Historian integration layer. Your guidance was significantly more sophisticated than what we initially built with Gemini 2.5 Flash and GPT-4.1-mini.

**What you recommended:**
- Ports-and-adapters architecture
- Decorator pattern for cross-cutting concerns
- Contract test suite to prevent mock drift
- Resilience (timeouts, retries, circuit breakers)
- Observability (health checks, audit logs)
- Hybrid search with domain-layer merge/rerank
- Developer tools (CLI, seed scripts)
- Configuration system with factory pattern

**What we actually built (Days 1-4):**
- Basic abstraction layer (HistorianClient interface)
- MockHistorianClient and InMemoryHistorianClient
- Simple RCRAG API with /rcrag/query endpoint
- Basic Historian data model (HistorianRecord, verification events)
- Lifecycle validation (proposal → execution_report → fact)

## Your Mission

Please review the existing code and create a comprehensive refactoring plan that elevates it to your recommended architecture.

## Existing Code Files

### 1. src/historian/historian_client.py
```python
from abc import ABC, abstractmethod
from typing import List, Optional
from .models import HistorianRecord

class HistorianClient(ABC):
    """Abstract interface for Historian implementations."""
    
    @abstractmethod
    async def create_record(self, record: HistorianRecord) -> str:
        """Create a new immutable record. Returns the record ID."""
        pass
    
    @abstractmethod
    async def get_record(self, record_id: str) -> Optional[HistorianRecord]:
        """Retrieve a record by ID."""
        pass
    
    @abstractmethod
    async def query_by_kind(self, kind: str, limit: int = 10) -> List[HistorianRecord]:
        """Query records by kind."""
        pass
    
    @abstractmethod
    async def query_by_provenance(self, source_id: str) -> List[HistorianRecord]:
        """Find all records that reference a source_id in provenance_ids."""
        pass
```

### 2. src/historian/models.py
```python
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime

@dataclass
class Evidence:
    source: str
    url: Optional[str] = None
    excerpt: Optional[str] = None
    confidence: float = 1.0

@dataclass
class HistorianRecord:
    id: str
    timestamp: str
    actor_id: str
    actor_type: str  # hub|manus|human|external
    kind: str  # proposal|execution_report|fact|artifact|verification_event
    subject: str
    summary: str
    body_md: str
    provenance_ids: List[str] = field(default_factory=list)
    status: str = "pending"  # pending|active|superseded|disputed|rejected
    evidence: List[Evidence] = field(default_factory=list)
    verification_event_ids: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
```

### 3. src/historian/inmemory_historian_client.py
(Basic in-memory implementation with async event loop issues)

### 4. src/main.py
```python
from fastapi import FastAPI
from historian.mock_historian_client import MockHistorianClient

app = FastAPI(title="RCRAG Service")

historian = MockHistorianClient()

@app.post("/rcrag/query")
async def rcrag_query(query: str, top_k: int = 3):
    """Query the Historian and return verified context."""
    context = await historian.search(query, top_k)
    
    # Apply Trust Policy filter
    trusted_context = [
        c for c in context 
        if c.get("trust_score", 0) > 0.85
    ]
    
    return {
        "query": query,
        "context": trusted_context,
        "trust_policy_applied": True
    }
```

## What We Need From You

### 1. Gap Analysis
- What are the key architectural gaps between what we built and your recommended design?
- What are the highest-priority improvements?
- What can we keep vs. what needs to be refactored?

### 2. Refactoring Plan
- Phase 1: What should we refactor first? (e.g., add decorator pattern)
- Phase 2: What comes next? (e.g., contract tests)
- Phase 3: What's the final state? (e.g., full observability)

### 3. Concrete Implementation Tasks
For each phase, provide:
- Specific files to create/modify
- Code patterns to implement
- Tests to write
- Configuration to add

### 4. Migration Strategy
- How do we refactor without breaking what's working?
- Can we do this incrementally?
- What's the risk/effort tradeoff?

### 5. Alignment with Sovereign Core Philosophy
- Does this refactoring align with "emergence through process"?
- Does it support the Dual-Layer Architecture (Inside/Outside)?
- Does it prevent the "Eye Cannot See the Eye" problem?

## Deliverable

Please provide a comprehensive refactoring plan document that includes:
1. Executive summary of the gaps
2. Phased refactoring roadmap
3. Concrete implementation tasks for each phase
4. Code examples for key patterns
5. Testing strategy
6. Migration/rollout plan
7. Philosophical alignment assessment

This plan will guide the next phase of our build, with you (GPT-5) as the primary architect and implementer.
