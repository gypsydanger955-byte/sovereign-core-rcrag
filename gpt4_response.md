```filename: requirements.txt
fastapi==0.95.2
uvicorn[standard]==0.22.0
pydantic==1.10.7
chromadb==0.3.21
python-dotenv==1.0.0
```

```filename: README.md
# Reality-Checked RAG (RCRAG) Service

## Overview

The RCRAG service is a critical component of the Sovereign Core's Dual-Layer Architecture. It provides verified, reality-grounded information to the internal Hub while preventing "Hallucination Cascades".

This repository contains the foundational scaffolding for the RCRAG service, including API endpoints, trust policy filtering, and configuration management.

---

## Requirements

- Python 3.11+
- All dependencies listed in `requirements.txt`

---

## Setup Instructions

1. **Clone the repository**

   ```bash
   git clone <repository-url>
   cd <repository-folder>
   ```

2. **Create and activate a virtual environment**

   ```bash
   python3.11 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**

   Create a `.env` file in the root directory or set environment variables directly. Example `.env`:

   ```
   CHROMADB_API_KEY=your_api_key_here
   CHROMADB_ENDPOINT=https://your-chromadb-instance
   ```

   The service currently supports configuration for ChromaDB client.

---

## Running the Service Locally

To start the FastAPI server with auto-reload:

```bash
uvicorn src.main:app --reload
```

The service will be available at `http://127.0.0.1:8000`.

---

## API Endpoints

### POST `/rcrag/query`

- **Request Body:**

  ```json
  {
    "question": "string",
    "scope": "string (optional)",
    "priority": "integer (optional)",
    "k": "integer (optional)"
  }
  ```

- **Response Body:**

  ```json
  {
    "answer_md": "string",
    "citations": ["string"],
    "latency_ms": "integer"
  }
  ```

### POST `/rcrag/submit-proposal`

- **Request Body:**

  ```json
  {
    "subject": "string",
    "summary": "string",
    "body_md": "string",
    "tags": ["string"]
  }
  ```

- **Response Body:**

  ```json
  {
    "id": "string"
  }
  ```

### POST `/rcrag/request-verification`

- **Request Body:**

  ```json
  {
    "proposal_id": "string",
    "method": "string"
  }
  ```

- **Response Body:**

  ```json
  {
    "report_id": "string",
    "status": "string"
  }
  ```

---

## Notes

- Currently, all endpoints return mock data.
- Trust policy filtering is implemented in `src/trust_policy.py`.
- Request and response validation is handled via Pydantic models in `src/models.py`.

---

## Contact

For questions or issues, please contact the primary developer.

```

```filename: src/config.py
"""
Configuration management for the RCRAG service.

Loads environment variables and provides typed access to configuration values.
"""

from pydantic import BaseSettings, Field


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    """

    chromadb_api_key: str | None = Field(
        default=None, env="CHROMADB_API_KEY", description="API key for ChromaDB client"
    )
    chromadb_endpoint: str | None = Field(
        default=None, env="CHROMADB_ENDPOINT", description="Endpoint URL for ChromaDB client"
    )
    # Add other configuration variables here as needed

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
```

```filename: src/models.py
"""
Pydantic models for request and response schemas of the RCRAG service.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    """
    Request model for POST /rcrag/query endpoint.
    """

    question: str = Field(..., description="The question to query")
    scope: Optional[str] = Field(None, description="Optional scope to limit the query")
    priority: Optional[int] = Field(None, ge=0, description="Optional priority level")
    k: Optional[int] = Field(None, ge=1, description="Number of top results to return")


class QueryResponse(BaseModel):
    """
    Response model for POST /rcrag/query endpoint.
    """

    answer_md: str = Field(..., description="Markdown formatted answer")
    citations: List[str] = Field(..., description="List of citation strings")
    latency_ms: int = Field(..., ge=0, description="Latency in milliseconds")


class SubmitProposalRequest(BaseModel):
    """
    Request model for POST /rcrag/submit-proposal endpoint.
    """

    subject: str = Field(..., description="Subject of the proposal")
    summary: str = Field(..., description="Summary of the proposal")
    body_md: str = Field(..., description="Markdown formatted body of the proposal")
    tags: List[str] = Field(..., description="List of tags associated with the proposal")


class SubmitProposalResponse(BaseModel):
    """
    Response model for POST /rcrag/submit-proposal endpoint.
    """

    id: str = Field(..., description="Unique identifier of the submitted proposal")


class RequestVerificationRequest(BaseModel):
    """
    Request model for POST /rcrag/request-verification endpoint.
    """

    proposal_id: str = Field(..., description="ID of the proposal to verify")
    method: str = Field(..., description="Verification method to use")


class RequestVerificationResponse(BaseModel):
    """
    Response model for POST /rcrag/request-verification endpoint.
    """

    report_id: str = Field(..., description="ID of the verification report")
    status: str = Field(..., description="Status of the verification request")
```

```filename: src/trust_policy.py
"""
Trust Policy filter implementation for the RCRAG service.
"""

from typing import List, Dict, Any


def apply_trust_policy(documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Filters a list of documents based on the trust policy.

    Trust policy criteria:
    - 'kind' must be one of ['execution_report', 'fact', 'artifact']
    - 'verified.status' must be 'accepted'

    Args:
        documents (List[Dict[str, Any]]): List of document dictionaries to filter.

    Returns:
        List[Dict[str, Any]]: List of documents that satisfy the trust policy.
    """
    allowed_kinds = {'execution_report', 'fact', 'artifact'}
    filtered_docs = []

    for doc in documents:
        kind = doc.get('kind')
        verified = doc.get('verified', {})
        status = verified.get('status')

        if kind in allowed_kinds and status == 'accepted':
            filtered_docs.append(doc)

    return filtered_docs
```

```filename: src/main.py
"""
FastAPI application for the Reality-Checked RAG (RCRAG) service.

Provides API endpoints with request validation and trust policy filtering.
"""

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import JSONResponse
from time import perf_counter
from typing import List

from src.models import (
    QueryRequest,
    QueryResponse,
    SubmitProposalRequest,
    SubmitProposalResponse,
    RequestVerificationRequest,
    RequestVerificationResponse,
)
from src.trust_policy import apply_trust_policy

app = FastAPI(
    title="Reality-Checked RAG (RCRAG) Service",
    description="Provides verified, reality-grounded information to the internal Hub while preventing Hallucination Cascades.",
    version="0.1.0",
)


@app.post(
    "/rcrag/query",
    response_model=QueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Query the RCRAG service",
    tags=["RCRAG"],
)
async def rcrag_query(request: QueryRequest) -> QueryResponse:
    """
    Handle a query request.

    Returns a mock answer with citations and latency.
    """
    start_time = perf_counter()

    # TODO: Implement actual query logic with ChromaDB client and trust policy filtering

    # Mock response data
    answer_md = f"**Answer to:** {request.question}"
    citations = ["doc1", "doc2"]
    latency_ms = int((perf_counter() - start_time) * 1000)

    return QueryResponse(answer_md=answer_md, citations=citations, latency_ms=latency_ms)


@app.post(
    "/rcrag/submit-proposal",
    response_model=SubmitProposalResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a new proposal",
    tags=["RCRAG"],
)
async def rcrag_submit_proposal(request: SubmitProposalRequest) -> SubmitProposalResponse:
    """
    Handle submission of a new proposal.

    Returns a mock unique proposal ID.
    """
    # TODO: Implement actual proposal storage and ID generation

    mock_id = "proposal-12345"
    return SubmitProposalResponse(id=mock_id)


@app.post(
    "/rcrag/request-verification",
    response_model=RequestVerificationResponse,
    status_code=status.HTTP_200_OK,
    summary="Request verification of a proposal",
    tags=["RCRAG"],
)
async def rcrag_request_verification(
    request: RequestVerificationRequest,
) -> RequestVerificationResponse:
    """
    Handle a verification request for a proposal.

    Returns a mock report ID and status.
    """
    # TODO: Implement actual verification logic

    mock_report_id = "report-67890"
    mock_status = "pending"

    return RequestVerificationResponse(report_id=mock_report_id, status=mock_status)
```