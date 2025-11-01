# Task for GPT-4: Implement Historian Abstraction Layer

## Context

Gemini (our strategic architect) has recommended that we implement an **Abstraction Layer** for the Historian integration. This will allow us to:
1. Build and test against a mock during scaffolding
2. Swap in real implementations (ChromaDB, Neo4j) later without changing the RCRAG service
3. Embody the "emergence through process" philosophy

## Gemini's Strategic Guidance (Summary)

> **Recommendation:** Build an abstraction layer (`HistorianClient` interface) with a `MockHistorianClient` implementation for scaffolding. This allows rapid iteration while maintaining clean architecture for future multi-database support.

## Your Mission

Implement the Historian abstraction layer with the following components:

### 1. `src/historian/historian_client.py`
- Abstract base class defining the contract for any Historian implementation
- Key method: `async def retrieve_context(query: str, top_k: int) -> List[Dict[str, Any]]`

### 2. `src/historian/mock_historian_client.py`
- Mock implementation with sample data about the Sovereign Core project
- Should simulate async operations
- Include mock trust scores for testing the Trust Policy

### 3. Update `src/main.py`
- Inject the `MockHistorianClient` into the RCRAG service
- Wire up the `/rcrag/query` endpoint to actually use the mock Historian
- Return real (mocked) data instead of hardcoded responses

### 4. Update `requirements.txt`
- Remove `chromadb==0.3.21` (as Gemini recommended)
- Keep all other dependencies

## Technical Requirements

- Use Python's `abc` module for the abstract base class
- Use `async/await` for all Historian operations
- Include type hints throughout
- Add comprehensive docstrings
- The mock data should be relevant to our project (Sovereign Core, RCRAG, etc.)

## Success Criteria

- The service can start without ChromaDB dependency errors
- The `/rcrag/query` endpoint returns context from the MockHistorianClient
- The Trust Policy filter works on the mock data
- The code is clean, well-documented, and follows the abstraction pattern

## Files to Create/Modify

1. **CREATE**: `src/historian/__init__.py`
2. **CREATE**: `src/historian/historian_client.py`
3. **CREATE**: `src/historian/mock_historian_client.py`
4. **MODIFY**: `src/main.py`
5. **MODIFY**: `requirements.txt`

Please implement this now. Provide the complete code for all files.
