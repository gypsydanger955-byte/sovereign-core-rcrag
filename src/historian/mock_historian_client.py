import asyncio
from typing import List, Dict, Any
from .historian_client import HistorianClient

class MockHistorianClient(HistorianClient):
    """
    A mock implementation of HistorianClient for scaffolding and testing.

    This mock client contains hardcoded historical records relevant to the
    Sovereign Core project and RCRAG. It simulates asynchronous retrieval
    and provides predictable data for development and testing.
    """

    def __init__(self) -> None:
        self._mock_data: List[Dict[str, Any]] = [
            {
                "id": "rec1",
                "content": "The first principle of Sovereign Core is self-sovereignty.",
                "source": "Core Docs",
                "timestamp": "2023-01-01T00:00:00Z",
                "trust_score": 0.95,
            },
            {
                "id": "rec2",
                "content": "RCRAG aims to prevent hallucinations by checking against trusted sources.",
                "source": "Project Brief",
                "timestamp": "2023-03-15T12:30:00Z",
                "trust_score": 0.90,
            },
            {
                "id": "rec3",
                "content": "ChromaDB requires a C++ compiler for installation and can cause build issues.",
                "source": "GPT-4 Chat",
                "timestamp": "2023-04-20T09:45:00Z",
                "trust_score": 0.80,
            },
            {
                "id": "rec4",
                "content": "Neo4j is excellent for relational knowledge graphs and supports complex queries.",
                "source": "Tech Blog",
                "timestamp": "2022-11-10T08:00:00Z",
                "trust_score": 0.75,
            },
            {
                "id": "rec5",
                "content": "The Council emphasized: 'The process is as important as the artifact'.",
                "source": "Council Meeting",
                "timestamp": "2023-04-22T15:00:00Z",
                "trust_score": 0.98,
            },
        ]

    async def retrieve_context(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Simulate retrieval of historical context by filtering mock data based on query.

        Args:
            query (str): The query string to search for.
            top_k (int, optional): Maximum number of records to return. Defaults to 5.

        Returns:
            List[Dict[str, Any]]: Filtered and sorted list of historical records.
        """
        print(f"MockHistorianClient: Retrieving context for query: '{query}'")
        await asyncio.sleep(0.05)  # Simulate async operation latency

        query_lower = query.lower()

        # Simple keyword match in 'content' or 'source'
        filtered = [
            record for record in self._mock_data
            if query_lower in record["content"].lower() or query_lower in record["source"].lower()
        ]

        # Sort by trust_score descending
        filtered.sort(key=lambda r: r.get("trust_score", 0.0), reverse=True)

        # Return top_k results
        return filtered[:top_k]

    # Optional store_record method for future use
    # async def store_record(self, record: Dict[str, Any]) -> str:
    #     print(f"MockHistorianClient: Storing record: {record}")
    #     self._mock_data.append(record)
    #     return record.get("id", f"mock_id_{len(self._mock_data)}")
