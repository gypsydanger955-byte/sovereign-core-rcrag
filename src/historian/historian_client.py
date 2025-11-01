from abc import ABC, abstractmethod
from typing import Optional, List
from src.historian.models import HistorianRecord


class HistorianClient(ABC):
    """
    Abstract base class for Historian clients.
    """

    @abstractmethod
    async def create_record(self, record: HistorianRecord) -> str:
        """
        Create a new immutable record. Returns the record ID.
        """
        raise NotImplementedError()

    @abstractmethod
    async def get_record(self, record_id: str) -> Optional[HistorianRecord]:
        """
        Retrieve a record by ID.
        """
        raise NotImplementedError()

    @abstractmethod
    async def query_by_kind(self, kind: str, limit: int = 10) -> List[HistorianRecord]:
        """
        Query records by kind.
        """
        raise NotImplementedError()

    @abstractmethod
    async def query_by_provenance(self, source_id: str) -> List[HistorianRecord]:
        """
        Find all records that reference a source_id in provenance_ids.
        """
        raise NotImplementedError()
