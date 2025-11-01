# Task for GPT-5: Implement Phase 1 Refactoring

## Context

You (GPT-5) have reviewed the existing RCRAG code and created a comprehensive refactoring plan. Now it's time to implement **Phase 1: Stabilize Core & Boundaries**.

## Phase 1 Goals

1. **Rename HistorianClient → HistorianPort** (proper ports-and-adapters naming)
2. **Implement decorator pattern** (Timeout, Retry, Logging)
3. **Move trust policy to application service** (RcragService)
4. **Fix async issues** in InMemory adapter
5. **Add contract tests** to prevent mock drift
6. **Create factory/configuration system** for composing the stack

## Your Mission

Implement the complete Phase 1 refactoring. Provide all the code files needed.

## File Structure to Create

```
src/rcrag/
├── domain/
│   ├── models.py                    # HistorianRecord, Evidence (dataclasses)
│   └── ports/
│       └── historian_port.py        # HistorianPort interface
├── application/
│   ├── trust_policy.py              # Trust policy logic
│   └── rcrag_service.py             # RcragService (orchestrates queries)
├── infrastructure/
│   ├── historian/
│   │   ├── inmemory_adapter.py      # InMemoryHistorianAdapter (fixed async)
│   │   ├── mock_adapter.py          # MockHistorianAdapter
│   │   └── decorators.py            # Timeout, Retry, Logging decorators
│   ├── config.py                    # Pydantic Settings
│   └── factory.py                   # build_historian(), build_services()
└── main.py                          # FastAPI app using factory

tests/
├── contract/
│   └── historian_port_contract_test.py  # Contract tests for all adapters
├── unit/
│   └── decorators_test.py               # Unit tests for decorators
├── application/
│   └── rcrag_service_test.py            # Application service tests
└── integration/
    └── main_route_test.py               # Integration tests for /rcrag/query
```

## Requirements

### 1. Domain Models (src/rcrag/domain/models.py)
- Move `HistorianRecord` and `Evidence` from `src/historian/models.py`
- Keep as dataclasses
- No changes to fields (maintain compatibility)

### 2. HistorianPort (src/rcrag/domain/ports/historian_port.py)
```python
from abc import ABC, abstractmethod
from typing import List, Optional
from ..models import HistorianRecord

class HistorianPort(ABC):
    """Port for Historian implementations (ports-and-adapters pattern)."""
    
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

### 3. Decorators (src/rcrag/infrastructure/historian/decorators.py)
Implement:
- `HistorianDecorator` (base class)
- `TimeoutDecorator` (uses `asyncio.wait_for`)
- `RetryDecorator` (exponential backoff with jitter)
- `LoggingDecorator` (structured logging with duration)

### 4. Adapters
- **InMemoryHistorianAdapter**: Fix async issues, use `asyncio.Lock` for state
- **MockHistorianAdapter**: Simple fake data for testing

### 5. Application Layer
- **TrustPolicy**: `compute_trust_score(record)` and `filter_context(records, threshold)`
- **RcragService**: `query(query: str, top_k: int)` method that orchestrates historian queries and applies trust policy

### 6. Configuration (src/rcrag/infrastructure/config.py)
```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    historian_adapter: str = "inmemory"  # mock|inmemory
    historian_timeout_s: float = 5.0
    historian_retries: int = 3
    historian_logging: bool = True
    trust_threshold: float = 0.85
    top_k_default: int = 3
    
    class Config:
        env_file = ".env"
```

### 7. Factory (src/rcrag/infrastructure/factory.py)
```python
def build_historian(cfg: Settings) -> HistorianPort:
    """Build historian with decorators based on config."""
    # Select adapter
    # Wrap with decorators (Timeout, Retry, Logging)
    # Return composed stack

def build_services(cfg: Settings):
    """Build application services."""
    historian = build_historian(cfg)
    trust_policy = TrustPolicy(threshold=cfg.trust_threshold)
    rcrag_service = RcragService(historian, trust_policy)
    return rcrag_service
```

### 8. FastAPI Integration (src/main.py)
```python
from fastapi import FastAPI, Depends
from rcrag.infrastructure.config import Settings
from rcrag.infrastructure.factory import build_services

app = FastAPI(title="RCRAG Service")
settings = Settings()
services = build_services(settings)

@app.post("/rcrag/query")
async def rcrag_query(query: str, top_k: int = settings.top_k_default):
    """Query the Historian and return verified context."""
    results = await services.query(query, top_k)
    return {
        "query": query,
        "results": [r.__dict__ for r in results],
        "trust_policy_applied": True
    }

@app.get("/health")
async def health():
    return {"status": "healthy", "historian": settings.historian_adapter}
```

### 9. Contract Tests (tests/contract/historian_port_contract_test.py)
```python
import pytest
from rcrag.infrastructure.historian.inmemory_adapter import InMemoryHistorianAdapter
from rcrag.infrastructure.historian.mock_adapter import MockHistorianAdapter

@pytest.mark.parametrize("adapter_class", [InMemoryHistorianAdapter, MockHistorianAdapter])
@pytest.mark.asyncio
async def test_create_and_get_record(adapter_class):
    """Contract test: all adapters must support create and get."""
    adapter = adapter_class()
    # Create a record
    # Get it back
    # Assert equality
    
@pytest.mark.parametrize("adapter_class", [InMemoryHistorianAdapter, MockHistorianAdapter])
@pytest.mark.asyncio
async def test_query_by_kind(adapter_class):
    """Contract test: query_by_kind returns correct records."""
    # Test implementation
```

## Deliverable

Please provide **complete, working code** for all files listed above. Use this format:

```filename: path/to/file.py
[complete file content]
```

Make sure:
- ✅ All imports are correct
- ✅ Async is handled properly (no event loop issues)
- ✅ Code is clean, documented, and follows best practices
- ✅ Tests are comprehensive and pass
- ✅ Configuration system works with environment variables

Generate the complete Phase 1 implementation now.
