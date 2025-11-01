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
