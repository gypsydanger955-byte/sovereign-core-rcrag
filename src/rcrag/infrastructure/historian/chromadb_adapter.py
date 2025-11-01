from typing import Any, Dict, List, Optional

try:
    import chromadb  # type: ignore
    CHROMA_AVAILABLE = True
except Exception:  # pragma: no cover - optional dependency
    CHROMA_AVAILABLE = False


class ChromaDBHistorianAdapter:
    """
    HistorianPort adapter using ChromaDB for vector storage and semantic search.

    Records are stored as:
    - id: string
    - document: textual content (from 'text' or 'content' key)
    - metadata: dict, should include 'kind' and any other attributes
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 8000,
        collection: str = "rcrag",
    ):
        if not CHROMA_AVAILABLE:  # pragma: no cover
            raise ImportError("chromadb is not installed")
        self._client = chromadb.HttpClient(host=host, port=port)  # type: ignore
        self._collection = self._client.get_or_create_collection(collection)

    async def create_record(self, record: Dict[str, Any]) -> str:
        rec_id = str(record.get("id") or record.get("record_id"))
        if not rec_id:
            raise ValueError("record requires 'id'")
        text: Optional[str] = record.get("text") or record.get("content")
        if text is None:
            text = str(record)
        metadata: Dict[str, Any] = dict(record.get("metadata") or {})
        if "kind" in record and "kind" not in metadata:
            metadata["kind"] = record["kind"]
        self._collection.add(ids=[rec_id], documents=[text], metadatas=[metadata])
        return rec_id

    async def get_record(self, record_id: str) -> Optional[Dict[str, Any]]:
        res = self._collection.get(ids=[record_id])
        if not res or not res.get("ids"):
            return None
        idx = 0
        return {
            "id": res["ids"][idx],
            "document": (res.get("documents") or [None])[idx],
            "metadata": (res.get("metadatas") or [None])[idx],
        }

    async def query_by_kind(self, kind: str) -> List[Dict[str, Any]]:
        res = self._collection.get(where={"kind": kind})
        ids: List[str] = res.get("ids") or []
        docs: List[str] = res.get("documents") or []
        metas: List[Dict[str, Any]] = res.get("metadatas") or []
        out: List[Dict[str, Any]] = []
        for i in range(len(ids)):
            out.append({"id": ids[i], "document": docs[i] if i < len(docs) else None, "metadata": metas[i] if i < len(metas) else None})
        return out

    async def semantic_search(self, query_text: str, top_k: int = 5) -> List[Dict[str, Any]]:
        q = self._collection.query(query_texts=[query_text], n_results=top_k)
        ids = (q.get("ids") or [[]])[0]
        docs = (q.get("documents") or [[]])[0]
        metas = (q.get("metadatas") or [[]])[0]
        out: List[Dict[str, Any]] = []
        for i in range(len(ids)):
            out.append({"id": ids[i], "document": docs[i] if i < len(docs) else None, "metadata": metas[i] if i < len(metas) else None})
        return out

    async def search(
        self,
        query: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 10,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Search with optional filters and pagination."""
        # Build where clause from filters
        where = {}
        if filters:
            if "kind" in filters:
                where["kind"] = filters["kind"]
        
        # If query provided, use semantic search
        if query:
            q = self._collection.query(
                query_texts=[query],
                n_results=limit + offset,
                where=where if where else None
            )
            ids = (q.get("ids") or [[]])[0]
            docs = (q.get("documents") or [[]])[0]
            metas = (q.get("metadatas") or [[]])[0]
        else:
            # No query, just filter-based retrieval
            res = self._collection.get(where=where if where else None)
            ids = res.get("ids") or []
            docs = res.get("documents") or []
            metas = res.get("metadatas") or []
        
        # Apply pagination
        start = max(0, offset)
        end = start + max(0, limit)
        ids = ids[start:end]
        docs = docs[start:end]
        metas = metas[start:end]
        
        out: List[Dict[str, Any]] = []
        for i in range(len(ids)):
            out.append({
                "id": ids[i],
                "document": docs[i] if i < len(docs) else None,
                "metadata": metas[i] if i < len(metas) else None
            })
        return out

    async def query_records(
        self,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 10,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Query records with filters and pagination."""
        where = {}
        if filters:
            if "kind" in filters:
                where["kind"] = filters["kind"]
        
        res = self._collection.get(where=where if where else None)
        ids = res.get("ids") or []
        docs = res.get("documents") or []
        metas = res.get("metadatas") or []
        
        # Apply pagination
        start = max(0, offset)
        end = start + max(0, limit)
        ids = ids[start:end]
        docs = docs[start:end]
        metas = metas[start:end]
        
        out: List[Dict[str, Any]] = []
        for i in range(len(ids)):
            out.append({
                "id": ids[i],
                "document": docs[i] if i < len(docs) else None,
                "metadata": metas[i] if i < len(metas) else None
            })
        return out
