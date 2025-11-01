# Investigation: Cache Decorator Missing Methods

## Smoking Gun #1: What methods does HistorianPort define?

## HistorianPort Interface
    async def create_record(self, record: HistorianRecord) -> str:
        """Create a new immutable record. Returns the record ID."""
        pass
--
    async def get_record(self, record_id: str) -> Optional[HistorianRecord]:
        """Retrieve a record by ID."""
        pass
--
    async def query_by_kind(self, kind: str, limit: int = 10) -> List[HistorianRecord]:
        """Query records by kind."""
        pass
--
    async def query_by_provenance(self, source_id: str) -> List[HistorianRecord]:
        """Find all records that reference a source_id in provenance_ids."""
        pass

## Smoking Gun #2: What methods are API routes calling?

        record_id = await historian.create_record(record)
            records = await historian.search(query=query, filters=filters, limit=limit)
            records = await historian.query_records(filters=filters, limit=limit)
        record = await historian.get_record(record_id)
        records = await historian.query_records(

## Smoking Gun #3: What methods does cache decorator override?


## Smoking Gun #4: What methods are MISSING?

Comparing HistorianPort interface vs cache decorator overrides...
