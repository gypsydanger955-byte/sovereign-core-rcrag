from typing import Any, Dict, List, Optional, Tuple

try:
    from neo4j import AsyncGraphDatabase  # type: ignore
    NEO4J_AVAILABLE = True
except Exception:  # pragma: no cover
    NEO4J_AVAILABLE = False


class Neo4jHistorianAdapter:
    """
    HistorianPort adapter using Neo4j for graph storage and provenance relationships.
    """

    def __init__(self, uri: str, user: str, password: str):
        if not NEO4J_AVAILABLE:  # pragma: no cover
            raise ImportError("neo4j is not installed")
        self._driver = AsyncGraphDatabase.driver(uri, auth=(user, password))

    async def close(self):
        await self._driver.close()

    async def create_record(self, record: Dict[str, Any]) -> str:
        rec_id = str(record.get("id") or record.get("record_id"))
        if not rec_id:
            raise ValueError("record requires 'id'")
        kind = record.get("kind")
        data = dict(record.get("data") or record.get("metadata") or {})
        text = record.get("text") or record.get("content")
        if text is not None:
            data["text"] = text

        cypher = """
            MERGE (n:Record {id: $id})
            ON CREATE SET n.kind = $kind, n += $data
            ON MATCH SET n.kind = coalesce(n.kind, $kind), n += $data
            RETURN n.id as id
        """
        async with self._driver.session() as session:
            result = await session.run(cypher, id=rec_id, kind=kind, data=data)
            rec = await result.single()
        return rec["id"]

    async def get_record(self, record_id: str) -> Optional[Dict[str, Any]]:
        cypher = "MATCH (n:Record {id: $id}) RETURN n"
        async with self._driver.session() as session:
            result = await session.run(cypher, id=record_id)
            row = await result.single()
        if row is None:
            return None
        node = row["n"]
        props = dict(node)  # type: ignore
        return {"id": props.pop("id", record_id), "kind": props.pop("kind", None), "data": props}

    async def query_by_kind(self, kind: str) -> List[Dict[str, Any]]:
        cypher = "MATCH (n:Record {kind: $kind}) RETURN n"
        out: List[Dict[str, Any]] = []
        async with self._driver.session() as session:
            result = await session.run(cypher, kind=kind)
            async for row in result:
                node = row["n"]
                props = dict(node)  # type: ignore
                out.append({"id": props.pop("id", None), "kind": props.pop("kind", None), "data": props})
        return out

    async def add_provenance(self, parent_id: str, child_id: str, relation: str = "PROV") -> Tuple[str, str]:
        cypher = f"""
            MATCH (p:Record {{id: $parent_id}}), (c:Record {{id: $child_id}})
            MERGE (p)-[r:{relation}]->(c)
            RETURN p.id as parent, c.id as child
        """
        async with self._driver.session() as session:
            result = await session.run(cypher, parent_id=parent_id, child_id=child_id)
            row = await result.single()
        return row["parent"], row["child"]

    async def get_provenance_chain(self, record_id: str, depth: int = 10) -> List[str]:
        cypher = """
            MATCH p = (n:Record {id: $id})-[:PROV*1..$depth]->(m)
            UNWIND nodes(p) as node
            RETURN DISTINCT node.id as id
        """
        async with self._driver.session() as session:
            result = await session.run(cypher, id=record_id, depth=depth)
            rows = [row["id"] async for row in result]
        # The first id is the starting record; include entire chain
        return rows

    async def search(
        self,
        query: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 10,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Search records with optional filters and pagination."""
        where_clauses = []
        params: Dict[str, Any] = {"limit": limit, "offset": offset}
        
        if filters and "kind" in filters:
            where_clauses.append("n.kind = $kind")
            params["kind"] = filters["kind"]
        
        if query:
            where_clauses.append("(n.text CONTAINS $query OR n.kind CONTAINS $query)")
            params["query"] = query
        
        where_str = " AND ".join(where_clauses) if where_clauses else "true"
        cypher = f"MATCH (n:Record) WHERE {where_str} RETURN n SKIP $offset LIMIT $limit"
        
        out: List[Dict[str, Any]] = []
        async with self._driver.session() as session:
            result = await session.run(cypher, **params)
            async for row in result:
                node = row["n"]
                props = dict(node)  # type: ignore
                out.append({
                    "id": props.pop("id", None),
                    "kind": props.pop("kind", None),
                    "data": props
                })
        return out

    async def query_records(
        self,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 10,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Query records with filters and pagination."""
        where_clauses = []
        params: Dict[str, Any] = {"limit": limit, "offset": offset}
        
        if filters and "kind" in filters:
            where_clauses.append("n.kind = $kind")
            params["kind"] = filters["kind"]
        
        where_str = " AND ".join(where_clauses) if where_clauses else "true"
        cypher = f"MATCH (n:Record) WHERE {where_str} RETURN n SKIP $offset LIMIT $limit"
        
        out: List[Dict[str, Any]] = []
        async with self._driver.session() as session:
            result = await session.run(cypher, **params)
            async for row in result:
                node = row["n"]
                props = dict(node)  # type: ignore
                out.append({
                    "id": props.pop("id", None),
                    "kind": props.pop("kind", None),
                    "data": props
                })
        return out
