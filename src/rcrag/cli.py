import json
from typing import Optional

import typer

from src.rcrag.infrastructure.config import Settings
from src.rcrag.infrastructure.factory import build_historian, build_service, configure_logging_from_settings
from src.rcrag.infrastructure.observability.health import check_liveness, check_readiness

app = typer.Typer(name="rcrag")


@app.command("seed")
def seed(
    records_file: Optional[str] = typer.Option(None, help="Path to JSONL file with records"),
):
    """
    Seed test records into historian. If no file provided, seeds a small default set.
    """
    settings = Settings()
    configure_logging_from_settings(settings)
    historian = build_historian(settings)

    # Determine seeding records
    records = []
    if records_file:
        with open(records_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
    else:
        records = [
            {"id": "1", "subject": "Solar farm proposal", "summary": "Proposal for 100MW solar farm", "body": "Details about solar farm", "metadata": {"state": "proposal"}},
            {"id": "2", "subject": "Execution report", "summary": "Report on execution progress", "body": "Construction reached 50%", "metadata": {"state": "execution_report"}},
            {"id": "3", "subject": "Operational facts", "summary": "Plant operational", "body": "Plant started operations", "metadata": {"state": "fact"}},
        ]
    # Historian port API is Phase 1; we best-effort insert
    for r in records:
        for method in ("add", "insert", "upsert", "save", "put"):
            fn = getattr(historian, method, None)
            if fn:
                try:
                    fn(r)
                    break
                except TypeError:
                    try:
                        fn(**r)
                        break
                    except Exception:  # pragma: no cover - minor ergonomics
                        continue
    typer.echo(f"Seeded {len(records)} records.")


@app.command("query")
def query(text: str = typer.Argument(..., help="Query text")):
    """
    Run a query through the RCRAG service.
    """
    settings = Settings()
    configure_logging_from_settings(settings)
    service = build_service(settings)
    # Phase 1 service is assumed to provide 'query' returning results
    result = service.query(text)  # type: ignore[attr-defined]
    # Attempt to serialize results
    try:
        from src.rcrag.api.schemas import HistorianRecordSchema
        records = [HistorianRecordSchema.from_domain(r) for r in getattr(result, "records", []) or getattr(result, "results", []) or []]  # type: ignore
        payload = {"query": text, "results": [r.dict() for r in records]}
    except Exception:
        payload = {"query": text, "result": str(result)}
    typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))


@app.command("health")
def health():
    """
    Check service health endpoints.
    """
    settings = Settings()
    configure_logging_from_settings(settings)
    historian = build_historian(settings)
    l_ok, _ = check_liveness()
    r_ok, msg = check_readiness(historian)
    typer.echo(json.dumps({"live": l_ok, "ready": r_ok, "message": msg}))


def run():
    app()


if __name__ == "__main__":
    run()
