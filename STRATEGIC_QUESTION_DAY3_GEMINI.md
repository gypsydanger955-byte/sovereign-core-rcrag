# Strategic Question for Gemini: Historian Data Model Design

## Context

We've successfully completed Days 1-2 (scaffolding) with a working abstraction layer. Now we need to implement the actual Historian data model and verification logic (Days 3-4).

**Current Status:**
- ✅ `HistorianClient` abstraction working
- ✅ `MockHistorianClient` functional
- ✅ RCRAG API service running
- 🔄 Need to implement the real data model

## The Challenge

We need to design the **Historian Data Model** that will be stored in ChromaDB (and potentially Neo4j). This model must:

1. **Distinguish proposals from verified facts** (prevent Hallucination Cascade)
2. **Support the Trust Policy** (filter by verification status)
3. **Enable evidence tracking** (SHA-256 hashes, signatures)
4. **Allow for audit trails** (who verified, when, how)
5. **Be flexible enough** for future enhancements

## The Proposed Schema (from our spec)

```json
{
  "id": "uuid",
  "timestamp": "RFC3339",
  "actor": "hub|manus|human|external",
  "kind": "proposal|execution_report|fact|artifact",
  "subject": "short slug",
  "summary": "1-2 sentence summary",
  "body_md": "full markdown or JSON payload",
  "evidence": [
    {
      "type": "log|api|file|url",
      "ref": "reference",
      "hash": "SHA-256",
      "signature": "optional"
    }
  ],
  "verified": {
    "by": "manus|human_auditor",
    "timestamp": "RFC3339",
    "method": "checklist|test|human_approval|external_api",
    "status": "accepted|rejected|inconclusive",
    "notes": "auditor notes"
  },
  "tags": ["topic/gpt5", "phase/outside-in"]
}
```

## Strategic Questions for You

1. **Is this schema sufficient?** What's missing? What could be improved?

2. **How should we handle the "proposal → execution_report" lifecycle?**
   - Should proposals reference their eventual execution_reports?
   - Should execution_reports reference the original proposals?
   - How do we prevent proposals from being "upgraded" to verified status?

3. **What about versioning?** If a fact changes over time, how do we handle it?
   - Immutable records with new versions?
   - Update-in-place with version history?

4. **ChromaDB vs Neo4j trade-offs:**
   - ChromaDB: Vector search, embeddings, semantic similarity
   - Neo4j: Relational graphs, complex queries, provenance chains
   - Should we use both? If so, how do they interact?

5. **Evidence hashing strategy:**
   - When do we compute hashes? (At ingestion? At verification?)
   - What if evidence changes? (e.g., a URL's content updates)
   - How do we handle large evidence files?

6. **Verification workflow:**
   - Who can mark something as verified? (Only Manus? Humans too?)
   - Can verification be revoked? (If new evidence contradicts it?)
   - How do we handle disputes?

## What I Need From You

1. **Your strategic recommendation** on the data model design
2. **Lifecycle management strategy** for proposals → execution_reports
3. **Database architecture** (ChromaDB only? ChromaDB + Neo4j? Something else?)
4. **Implementation priorities** (What should we build first in Days 3-4?)

## Additional Context

- The Council emphasized: "Verification is a collaborative virtue, not an imposed constraint"
- Claude warned: "Over-reliance on the Executor could create a single point of failure"
- We want to build something that scales and evolves gracefully

Please provide your strategic guidance for Days 3-4.
