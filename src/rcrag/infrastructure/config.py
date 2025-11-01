from typing import Literal, Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Existing settings from Phases 1/2 are assumed present; we add new ones with defaults.

    # OpenTelemetry
    otel_enabled: bool = False
    otel_exporter_endpoint: Optional[str] = None  # e.g. http://otel-collector:4318/v1/traces
    otel_service_name: str = "rcrag-service"

    # Prometheus
    prometheus_enabled: bool = True

    # Cache
    cache_enabled: bool = True
    cache_ttl_seconds: float = 30.0
    cache_max_size: int = 1024

    # Rate limiting
    rate_limit_enabled: bool = False
    rate_limit_requests_per_second: float = 10.0
    rate_limit_burst_size: int = 20

    # Historian adapters
    historian_adapter: Literal["memory", "chromadb", "neo4j"] = "memory"

    # ChromaDB
    chromadb_host: str = "localhost"
    chromadb_port: int = 8000
    chromadb_collection: str = "rcrag"

    # Neo4j
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "password"

    class Config:
        env_prefix = "RCRAG_"
        case_sensitive = False
