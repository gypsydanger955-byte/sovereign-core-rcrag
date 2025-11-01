import io
import json
import logging

from src.rcrag.infrastructure.audit import AuditLogger
from src.rcrag.infrastructure.logging import set_correlation_id


class Record:
    def __init__(self, id):
        self.id = id


def test_audit_emits_events_with_correlation_id():
    # Capture audit logger output in-memory
    log_stream = io.StringIO()
    handler = logging.StreamHandler(log_stream)
    logger = logging.getLogger("audit-test")
    logger.setLevel(logging.INFO)
    logger.handlers = [handler]

    audit = AuditLogger(logger=logger, policy_version="v1")
    set_correlation_id("cid-123")
    audit.log_query(query="hello", selected_records=[Record("1"), Record("2")], trust_scores={"1": 0.9})

    handler.flush()
    contents = log_stream.getvalue().strip()
    assert contents, "No audit output"

    # Expect JSON payload
    payload = json.loads(contents)
    assert payload["event"] == "query"
    assert payload["policy_version"] == "v1"
    assert payload["correlation_id"] == "cid-123"
    assert payload["query"] == "hello"
    assert payload["selected_record_ids"] == ["1", "2"]
    assert payload["trust_scores"] == {"1": 0.9}
