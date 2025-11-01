from typing import Any

from src.rcrag.infrastructure.config import Settings
from src.rcrag.infrastructure.observability.metrics import init_prometheus
from src.rcrag.infrastructure.observability.tracing import init_tracing

# Optional imports for adapters and decorators
try:
    from src.rcrag.infrastructure.historian.chromadb_adapter import ChromaDBHistorianAdapter  # type: ignore
except Exception:  # pragma: no cover
    ChromaDBHistorianAdapter = None  # type: ignore

try:
    from src.rcrag.infrastructure.historian.neo4j_adapter import Neo4jHistorianAdapter  # type: ignore
except Exception:  # pragma: no cover
    Neo4jHistorianAdapter = None  # type: ignore

try:
    from src.rcrag.infrastructure.historian.cache_decorator import CacheHistorianDecorator
except Exception:  # pragma: no cover
    CacheHistorianDecorator = None  # type: ignore

try:
    from src.rcrag.infrastructure.historian.rate_limit_decorator import RateLimitHistorianDecorator
except Exception:  # pragma: no cover
    RateLimitHistorianDecorator = None  # type: ignore


def init_observability(app: Any, settings: Settings) -> None:
    init_tracing(
        service_name=settings.otel_service_name,
        exporter_endpoint=settings.otel_exporter_endpoint,
        app=app,
        enabled=settings.otel_enabled,
    )
    init_prometheus(app, enabled=settings.prometheus_enabled)


def build_historian(settings: Settings, fallback_historian: Any = None) -> Any:
    """
    Build historian adapter based on configuration and wrap with decorators.
    If fallback_historian is provided and adapter is unknown/unavailable, it will be used.
    """
    adapter = None

    if settings.historian_adapter == "chromadb" and ChromaDBHistorianAdapter is not None:
        adapter = ChromaDBHistorianAdapter(
            host=settings.chromadb_host,
            port=settings.chromadb_port,
            collection=settings.chromadb_collection,
        )
    elif settings.historian_adapter == "neo4j" and Neo4jHistorianAdapter is not None:
        adapter = Neo4jHistorianAdapter(
            uri=settings.neo4j_uri,
            user=settings.neo4j_user,
            password=settings.neo4j_password,
        )
    else:
        adapter = fallback_historian

    # Decorators
    if adapter is not None and settings.rate_limit_enabled and RateLimitHistorianDecorator is not None:
        adapter = RateLimitHistorianDecorator(
            adapter,
            rate_per_second=settings.rate_limit_requests_per_second,
            burst_size=settings.rate_limit_burst_size,
        )

    if adapter is not None and settings.cache_enabled and CacheHistorianDecorator is not None:
        adapter = CacheHistorianDecorator(
            adapter,
            ttl_seconds=settings.cache_ttl_seconds,
            max_size=settings.cache_max_size,
        )

    return adapter
