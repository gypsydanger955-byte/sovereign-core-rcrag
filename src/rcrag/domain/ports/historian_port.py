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
        limit: int = 10
    ) -> List[HistorianRecord]:
        """Search records with optional query string and filters."""
        pass

    @abstractmethod
    async def query_records(
        self,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 10
    ) -> List[HistorianRecord]:
        """Query records with filters (kind, metadata, etc.)."""
        pass
