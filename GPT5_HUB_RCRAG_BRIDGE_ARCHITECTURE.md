# Hub-RCRAG API Bridge Architecture Proposal

---

## 1. Architecture Overview

### 1.1 Client Library Structure

```
hub_rcrag/
│
├── __init__.py
├── client.py                # Main RCRAGClient class
├── models.py                # Pydantic models for requests/responses
├── exceptions.py            # Custom exceptions for error handling
├── utils.py                 # Retry logic, HTTP helpers
├── config.py                # Configuration dataclasses
└── tests/
    ├── __init__.py
    ├── test_client.py
    ├── test_models.py
    └── test_integration.py
```

### 1.2 Key Classes and Responsibilities

| Class / Module      | Responsibility                                                                                  |
|--------------------|------------------------------------------------------------------------------------------------|
| `RCRAGClient`       | Async client exposing public API methods for storing, searching, and retrieving records.       |
| `models.py`         | Pydantic models for request bodies, responses, and record representation.                       |
| `exceptions.py`     | Define custom exceptions (e.g., `RCRAGAPIError`, `NetworkError`, `TimeoutError`) for clarity.  |
| `utils.py`          | Helper functions: retry logic with exponential backoff, HTTP request wrappers.                 |
| `config.py`         | Configuration classes for client initialization (timeouts, retries, base_url, etc.)            |

### 1.3 Data Flow

1. Hub agent calls async method on `RCRAGClient`.
2. Client validates inputs using Pydantic models.
3. Client sends HTTP request to RCRAG/Historian API endpoints asynchronously.
4. Handles retries on network failures/timeouts automatically.
5. Parses JSON response into Pydantic response models.
6. Returns domain models or raises clear exceptions on errors.

---

## 2. API Design

### 2.1 Client Class Interface

```python
from typing import Optional, List, Dict, Any
from pydantic import BaseModel

class RCRAGClient:
    def __init__(
        self,
        base_url: str,
        timeout: float = 10.0,
        max_retries: int = 3,
        retry_backoff_factor: float = 0.5,
    ):
        """
        Initialize the RCRAG client.

        Args:
            base_url: Base URL of RCRAG/Historian API.
            timeout: Request timeout in seconds.
            max_retries: Number of retries on network failure.
            retry_backoff_factor: Backoff multiplier between retries.
        """

    async def store_record(
        self,
        content: str,
        kind: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Store a record and return its ID.

        Args:
            content: Text content of the record.
            kind: Type/category of the record.
            metadata: Optional additional metadata.

        Returns:
            Record ID as string.
        """

    async def search(
        self,
        query: str,
        kind: Optional[str] = None,
        limit: int = 10,
        offset: int = 0,
    ) -> List["RecordSummary"]:
        """
        Search records by query and kind.

        Args:
            query: Search query string.
            kind: Optional filter by kind.
            limit: Max number of results to return.
            offset: Pagination offset.

        Returns:
            List of RecordSummary items.
        """

    async def get_record(self, record_id: str) -> "Record":
        """
        Retrieve full details of a record.

        Args:
            record_id: ID of the record.

        Returns:
            Record instance.
        """
```

### 2.2 Request/Response Models (Pydantic)

```python
from pydantic import BaseModel
from typing import Optional, Dict, Any, List

class Record(BaseModel):
    id: str
    content: str
    kind: str
    metadata: Optional[Dict[str, Any]]
    created_at: Optional[str]  # ISO datetime string

class RecordSummary(BaseModel):
    id: str
    kind: str
    snippet: Optional[str]            # Optional short preview of content
    metadata: Optional[Dict[str, Any]]

class StoreRecordRequest(BaseModel):
    content: str
    kind: str
    metadata: Optional[Dict[str, Any]]

class StoreRecordResponse(BaseModel):
    id: str

class SearchRecordsResponse(BaseModel):
    results: List[RecordSummary]
    total: int
    limit: int
    offset: int
```

---

## 3. Implementation Plan

### 3.1 File Structure

- `hub_rcrag/client.py`  
  Implements `RCRAGClient` with async HTTP calls using `httpx.AsyncClient`.

- `hub_rcrag/models.py`  
  Pydantic models as above.

- `hub_rcrag/exceptions.py`  
  Custom exceptions like `RCRAGAPIError`, `NetworkError`.

- `hub_rcrag/utils.py`  
  Retry decorator/function using exponential backoff.

- `hub_rcrag/config.py`  
  Data classes for configuration parameters if needed.

- `hub_rcrag/tests/`  
  Unit + integration tests using `pytest`, with `respx` or `aioresponses` for HTTP mocking.

### 3.2 Dependencies

- `httpx>=0.23` (async HTTP client)
- `pydantic>=1.10`
- `pytest` (testing)
- `respx` or `aioresponses` for HTTP mocking
- `tenacity` (optional for retry logic, or custom)

### 3.3 Key Implementation Details

- Use `httpx.AsyncClient` for all HTTP calls with configured timeouts.
- Implement retry logic via decorator or helper function in `utils.py`, retrying on network errors and 5xx errors with exponential backoff.
- Deserialize JSON responses into Pydantic models.
- On 4xx errors, raise informative exceptions with error message from API.
- Support pagination in `search()` with `limit` and `offset`.
- Cache: **No client-side caching initially** — keep client stateless and simple.
- Batch operations: **Not supported in initial version**, can be added later as needed.
- Streaming: **Not supported initially**, pagination handles large result sets.
- Error surface: Exceptions derived from base `RCRAGAPIError` with clear messages.

---

## 4. Usage Examples

```python
import asyncio
from hub_rcrag import RCRAGClient, RCRAGAPIError

async def main():
    client = RCRAGClient(base_url="https://http--rcrag-service--46m65wlq8tb2.code.run", timeout=10, max_retries=3)

    # Store a record
    try:
        record_id = await client.store_record(
            content="GPT-5 proposed an async-first client library.",
            kind="technical_proposal",
            metadata={"author": "gpt5", "project": "rcrag"}
        )
        print(f"Stored record ID: {record_id}")
    except RCRAGAPIError as e:
        print(f"Failed to store record: {e}")

    # Search records
    try:
        results = await client.search(query="cache decorator", kind="technical_proposal", limit=5)
        for r in results:
            print(f"Found record: {r.id} kind={r.kind}")
    except RCRAGAPIError as e:
        print(f"Search failed: {e}")

    # Get a record
    try:
        record = await client.get_record(record_id)
        print(f"Record content: {record.content}")
    except RCRAGAPIError as e:
        print(f"Get record failed: {e}")

asyncio.run(main())
```

### Best Practices

- Use `async with RCRAGClient(...) as client:` if implemented to manage lifecycle.
- Catch `RCRAGAPIError` to handle all API-related failures gracefully.
- Use pagination parameters when searching large datasets.
- Avoid caching at client side for consistency; let agents implement any caching if needed.

---

## 5. Testing Strategy

### 5.1 Unit Tests

- Test each public method (`store_record`, `search`, `get_record`) with mocked HTTP responses.
- Validate Pydantic model parsing and serialization.
- Test retry logic by simulating transient failures.
- Test exception raising on HTTP 4xx/5xx.

### 5.2 Integration Tests

- Run against a test instance or mock server of RCRAG service.
- Verify end-to-end request/response flow.
- Test pagination and error flows.

### 5.3 Mock Strategies

- Use `respx` (preferred) or `aioresponses` to mock async HTTPX requests.
- Mock retries by triggering network errors and ensuring client retries as expected.
- Mock API error responses with various HTTP codes and payloads.

---

## Questions Addressed

| Question                               | Answer                                                                                   |
|--------------------------------------|------------------------------------------------------------------------------------------|
| 1. Should the client handle retries automatically? | **Yes.** Retries on network issues and 5xx errors with exponential backoff for robustness. |
| 2. Should we cache responses on the client side?   | **No, initially no caching.** Keep client stateless and simple; agents may cache if needed.  |
| 3. How should we handle large result sets?         | Use **pagination** with `limit` and `offset` parameters in `search()`. No streaming initially. |
| 4. Should we support batch operations?             | Not in initial version. Can add later if agent workflows require it.                      |
| 5. How should errors be surfaced to agents?        | Via **custom exceptions** with clear messages, all inheriting from a base `RCRAGAPIError`.  |

---

# Summary

This design delivers a clean, async-first, type-safe Python client library for Hub agents to interact with the RCRAG/Historian API with robust error handling and simple usage patterns. It balances simplicity with extensibility and is ready for future features like authentication, caching, and batch operations without complicating the initial interface.

---

If you want, I can provide a detailed code skeleton or a fully working minimal client implementation next.