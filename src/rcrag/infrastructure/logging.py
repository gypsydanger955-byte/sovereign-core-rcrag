import json
import logging
import sys
import time
import uuid
from contextvars import ContextVar
from typing import Any, Dict, Optional

try:
    from pydantic import BaseModel
except Exception:  # pragma: no cover
    BaseModel = object  # type: ignore


correlation_id_ctx: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)


def set_correlation_id(value: Optional[str]) -> None:
    correlation_id_ctx.set(value)


def get_correlation_id() -> Optional[str]:
    return correlation_id_ctx.get()


class CorrelationIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        setattr(record, "correlation_id", get_correlation_id())
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "ts": getattr(record, "ts", None) or time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Include common fields if available
        for field in ("correlation_id", "request_path", "request_method", "status_code", "duration_ms"):
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        # Include extras
        if record.args and isinstance(record.args, dict):
            payload.update(record.args)
        # Include exception info if present
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(
    level: str = "INFO",
    fmt: str = "json",
    audit_log_file: Optional[str] = None,
) -> None:
    """
    Configure root and uvicorn loggers with structured logging and correlation ID filter.
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    root = logging.getLogger()
    root.setLevel(log_level)
    for h in list(root.handlers):
        root.removeHandler(h)

    handler: logging.Handler
    if fmt.lower() == "json":
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
    else:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s [cid=%(correlation_id)s] %(message)s"))

    handler.addFilter(CorrelationIdFilter())
    root.addHandler(handler)

    # Uvicorn loggers (if used)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "fastapi"):
        lg = logging.getLogger(name)
        lg.setLevel(log_level)
        lg.handlers = []
        lg.addHandler(handler)
        lg.propagate = False

    # Audit logger setup
    audit_logger = logging.getLogger("audit")
    audit_logger.setLevel(log_level)
    audit_logger.handlers = []
    if audit_log_file:
        file_handler = logging.FileHandler(audit_log_file)
        if fmt.lower() == "json":
            file_handler.setFormatter(JsonFormatter())
        else:
            file_handler.setFormatter(logging.Formatter("%(asctime)s AUDIT [cid=%(correlation_id)s] %(message)s"))
        file_handler.addFilter(CorrelationIdFilter())
        audit_logger.addHandler(file_handler)
    else:
        audit_logger.addHandler(handler)


class RequestLoggingMiddleware:
    """
    FastAPI/Starlette middleware that assigns correlation IDs and logs requests.
    """

    def __init__(self, app, header_name: str = "X-Request-ID") -> None:
        self.app = app
        self.header_name = header_name

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        start = time.time()
        # Extract or generate correlation ID
        headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
        corr_id = headers.get(self.header_name.lower())
        if not corr_id:
            corr_id = str(uuid.uuid4())
        token = correlation_id_ctx.set(corr_id)

        # Intercept send to capture status code
        status_code_container = {"code": None}

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status_code_container["code"] = message["status"]
            return await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration_ms = int((time.time() - start) * 1000)
            path = scope.get("path")
            method = scope.get("method")
            logger = logging.getLogger("http")
            extra = logging.LoggerAdapter(logger, {})
            # Use log record extras
            record = logging.LogRecord(
                name="http",
                level=logging.INFO,
                pathname=__file__,
                lineno=0,
                msg=f"{method} {path}",
                args=(),
                exc_info=None,
            )
            record.request_path = path
            record.request_method = method
            record.status_code = status_code_container["code"]
            record.duration_ms = duration_ms
            CorrelationIdFilter().filter(record)
            if root := logging.getLogger():
                for h in root.handlers:
                    h.handle(record)
            correlation_id_ctx.reset(token)
