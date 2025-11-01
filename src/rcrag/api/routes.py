"""API routes for RCRAG Historian service."""
from typing import Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.rcrag.infrastructure.factory import build_historian
from src.rcrag.infrastructure.config import Settings
from src.rcrag.infrastructure.historian.inmemory_adapter import InMemoryHistorianAdapter
from src.rcrag.domain.models import HistorianRecord


# Request/Response models
class StoreRecordRequest(BaseModel):
    """Request to store a record in Historian."""
    content: str = Field(..., description="The content to store")
    kind: str = Field(..., description="The type/kind of record")
    metadata: Dict = Field(default_factory=dict, description="Additional metadata")


class StoreRecordResponse(BaseModel):
    """Response after storing a record."""
    record_id: str = Field(..., description="The ID of the stored record")
    status: str = Field(default="success")


class SearchRecordsResponse(BaseModel):
    """Response for search query."""
    records: List[Dict] = Field(..., description="List of matching records")
    count: int = Field(..., description="Number of records returned")


class GetRecordResponse(BaseModel):
    """Response for getting a single record."""
    record_id: str
    content: str
    kind: str
    metadata: Dict
    created_at: Optional[str] = None


# Create router
router = APIRouter(prefix="/api/v1", tags=["historian"])


# Initialize historian (will be done per request for now)
# Use a module-level instance to persist data across requests
_historian_instance = None

def get_historian():
    """Get historian instance."""
    global _historian_instance
    if _historian_instance is None:
        settings = Settings()
        # Use InMemoryAdapter as fallback if no adapter configured
        fallback = InMemoryHistorianAdapter()
        _historian_instance = build_historian(settings, fallback_historian=fallback)
    return _historian_instance


@router.post("/records", response_model=StoreRecordResponse)
async def store_record(request: StoreRecordRequest):
    """
    Store a new record in Historian.
    
    **Parameters:**
    - content: The content to store
    - kind: The type/kind of record (e.g., "technical_proposal", "code_review")
    - metadata: Additional metadata as key-value pairs
    
    **Returns:**
    - record_id: The ID of the stored record
    """
    try:
        historian = get_historian()
        record = HistorianRecord(
            content=request.content,
            kind=request.kind,
            metadata=request.metadata
        )
        record_id = await historian.create_record(record)
        return StoreRecordResponse(record_id=record_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to store record: {str(e)}")


@router.get("/records/search", response_model=SearchRecordsResponse)
async def search_records(
    query: Optional[str] = Query(None, description="Search query"),
    kind: Optional[str] = Query(None, description="Filter by record kind"),
    limit: int = Query(10, ge=1, le=100, description="Maximum number of results")
):
    """
    Search for records in Historian.
    
    **Parameters:**
    - query: Optional search query string
    - kind: Optional filter by record kind
    - limit: Maximum number of results (1-100)
    
    **Returns:**
    - records: List of matching records
    - count: Number of records returned
    """
    try:
        historian = get_historian()
        
        # Build filters
        filters = {}
        if kind:
            filters["kind"] = kind
        
        # Search records
        if query:
            records = await historian.search(query=query, filters=filters, limit=limit)
        else:
            # If no query, just filter by kind
            records = await historian.query_records(filters=filters, limit=limit)
        
        return SearchRecordsResponse(
            records=records,
            count=len(records)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to search records: {str(e)}")


@router.get("/records/{record_id}", response_model=GetRecordResponse)
async def get_record(record_id: str):
    """
    Get a specific record by ID.
    
    **Parameters:**
    - record_id: The ID of the record to retrieve
    
    **Returns:**
    - Record details including content, kind, and metadata
    """
    try:
        historian = get_historian()
        record = await historian.get_record(record_id)
        
        if not record:
            raise HTTPException(status_code=404, detail=f"Record {record_id} not found")
        
        return GetRecordResponse(
            record_id=record.id,
            content=record.content,
            kind=record.kind,
            metadata=record.metadata,
            created_at=record.created_at.isoformat() if hasattr(record.created_at, 'isoformat') else str(record.created_at)
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get record: {str(e)}")


@router.get("/records", response_model=SearchRecordsResponse)
async def list_records(
    kind: Optional[str] = Query(None, description="Filter by record kind"),
    limit: int = Query(10, ge=1, le=100, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of records to skip")
):
    """
    List records with optional filtering.
    
    **Parameters:**
    - kind: Optional filter by record kind
    - limit: Maximum number of results (1-100)
    - offset: Number of records to skip
    
    **Returns:**
    - records: List of records
    - count: Number of records returned
    """
    try:
        historian = get_historian()
        
        filters = {}
        if kind:
            filters["kind"] = kind
        
        records = await historian.query_records(
            filters=filters,
            limit=limit,
            offset=offset
        )
        
        return SearchRecordsResponse(
            records=records,
            count=len(records)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list records: {str(e)}")


@router.get("/stats")
async def get_stats():
    """
    Get statistics about the Historian service.
    
    **Returns:**
    - Statistics including record counts by kind
    """
    try:
        historian = get_historian()
        
        # Get basic stats
        stats = {
            "status": "operational",
            "service": "historian",
            "version": "1.0.0"
        }
        
        # Try to get record counts if historian supports it
        try:
            if hasattr(historian, 'get_stats'):
                historian_stats = await historian.get_stats()
                stats.update(historian_stats)
        except:
            pass
        
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")
