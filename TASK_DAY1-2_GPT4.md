# Task for GPT-4: Days 1-2 - RCRAG Service Scaffolding

## Context

You are the primary coder for the Reality-Checked RAG (RCRAG) service, a critical component of the Sovereign Core's Dual-Layer Architecture. This service will provide verified, reality-grounded information to the internal Hub while preventing "Hallucination Cascades."

## Your Mission (Days 1-2)

Create the foundational scaffolding for the RCRAG service, including:
1. Project structure and dependencies
2. Core API endpoints (stubs with proper routing)
3. Trust Policy filter implementation
4. Basic request/response validation

## Technical Requirements

**Stack:**
- Python 3.11+
- FastAPI for the REST API
- Pydantic for data validation
- ChromaDB client for Historian access

**API Endpoints to Implement (Stubs):**

1. `POST /rcrag/query`
   - Request: `{question, scope?, priority?, k?}`
   - Response: `{answer_md, citations[], latency_ms}`

2. `POST /rcrag/submit-proposal`
   - Request: `{subject, summary, body_md, tags[]}`
   - Response: `{id}`

3. `POST /rcrag/request-verification`
   - Request: `{proposal_id, method}`
   - Response: `{report_id, status}`

**Trust Policy Filter:**

Implement a function `apply_trust_policy(documents)` that filters documents based on:
- `kind` must be in `['execution_report', 'fact', 'artifact']`
- `verified.status` must be `'accepted'`

## Deliverables

1. **`src/main.py`** - FastAPI application with all three endpoint stubs
2. **`src/models.py`** - Pydantic models for all request/response schemas
3. **`src/trust_policy.py`** - Trust Policy filter implementation
4. **`src/config.py`** - Configuration management (environment variables, etc.)
5. **`requirements.txt`** - All Python dependencies
6. **`README.md`** - Setup and run instructions

## Success Criteria

- All endpoints return proper HTTP status codes
- Request validation works correctly (reject malformed requests)
- Trust Policy filter correctly identifies vetted vs unvetted documents
- Service can be run locally with `uvicorn src.main:app --reload`

## Notes

- For now, endpoints can return mock data
- Focus on clean, well-documented code
- Use type hints throughout
- Include docstrings for all functions

Please implement this scaffolding now. I will then pass your code to Claude for review.
