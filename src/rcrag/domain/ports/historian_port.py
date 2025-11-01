from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
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

    @abstractmethod
    async def search(
        self,
        query: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 10,
        offset: int = 0
    ) -> List[HistorianRecord]:
        """
        Search records with optional query string and filters.
        
        Args:
            query: Search query string (case-insensitive substring match)
            filters: Dict of filters with implicit AND semantics
            limit: Maximum number of records to return
            offset: Number of records to skip (for pagination)
            
        Returns:
            List of matching HistorianRecord objects
        """
        pass

    @abstractmethod
    async def query_records(
        self,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 10,
        offset: int = 0
    ) -> List[HistorianRecord]:
        """
        Query records with filters using implicit AND semantics.
        
        Args:
            filters: Dict of filters to apply. Supported keys:
                - 'kind': exact match on record.kind
                - 'namespace': exact match on record.namespace
                - 'metadata': dict of key->value; all must match in record.metadata
                - 'created_after': ISO-8601 timestamp; record.created_at > value
                - 'created_before': ISO-8601 timestamp; record.created_at < value
            limit: Maximum number of records to return
            offset: Number of records to skip (for pagination)
            
        Returns:
            List of matching HistorianRecord objects
            
        Note:
            Ordering stability is not guaranteed unless the underlying adapter
            sorts by a stable field. Clients should accept eventual consistency
            or use cursor/keyset pagination in future enhancements.
        """
        pass
