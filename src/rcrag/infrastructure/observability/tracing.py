import logging
import os
from typing import Optional

try:
    from opentelemetry import trace
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    OTEL_AVAILABLE = True
except Exception:  # pragma: no cover - optional dependency
    OTEL_AVAILABLE = False

try:
    from opentelemetry.trace import get_current_span
except Exception:  # pragma: no cover
    def get_current_span():
        return None


class _OTelLoggingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            span = get_current_span()
            ctx = getattr(span, "get_span_context", lambda: None)()
            if ctx is not None and getattr(ctx, "is_valid", False):
                trace_id = getattr(ctx, "trace_id", 0)
                span_id = getattr(ctx, "span_id", 0)
                record.otelTraceID = f"{trace_id:032x}"
                record.otelSpanID = f"{span_id:016x}"
            else:
                record.otelTraceID = "-"
                record.otelSpanID = "-"
        except Exception:  # pragma: no cover
            record.otelTraceID = "-"
            record.otelSpanID = "-"
        return True


def setup_logging_trace_context() -> None:
    """
    Adds trace context to all standard logging records using fields:
    - %(otelTraceID)s
    - %(otelSpanID)s
    """
    root = logging.getLogger()
    # Avoid duplicate filters
    for f in root.filters:
        if isinstance(f, _OTelLoggingFilter):
            return
    root.addFilter(_OTelLoggingFilter())


def init_tracing(
    service_name: str,
    exporter_endpoint: Optional[str] = None,
    app=None,
    enabled: bool = True,
) -> None:
    """
    Initialize OpenTelemetry tracing:
    - Configure SDK, Resource, OTLP exporter
    - Instrument FastAPI (if provided)
    - Add trace context to logging records
    """
    if not enabled:
        return

    if not OTEL_AVAILABLE:  # pragma: no cover - environment without OTel
        setup_logging_trace_context()
        return

    # Setup provider and exporter
    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)
    if exporter_endpoint:
        # Allow overriding via env if set
        os.environ.setdefault("OTEL_EXPORTER_OTLP_ENDPOINT", exporter_endpoint)
        exporter = OTLPSpanExporter(endpoint=exporter_endpoint)
        processor = BatchSpanProcessor(exporter)
        provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)

    # Instrument FastAPI app if provided
    if app is not None:
        try:
            FastAPIInstrumentor.instrument_app(app)
        except Exception:  # pragma: no cover
            pass

    setup_logging_trace_context()


def get_tracer(name: str = "src.rcrag"):

    if OTEL_AVAILABLE:
        return trace.get_tracer(name)
    # Fallback tracer shim
    class _NoopSpan:
        def __enter__(self): return self
        def __exit__(self, exc_type, exc, tb): return False
        async def __aenter__(self): return self
        async def __aexit__(self, exc_type, exc, tb): return False

    class _NoopTracer:
        def start_as_current_span(self, *_args, **_kwargs):
            return _NoopSpan()
    return _NoopTracer()
