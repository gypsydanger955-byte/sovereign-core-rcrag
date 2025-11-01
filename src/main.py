import logging

from fastapi import FastAPI

from src.rcrag.infrastructure.config import Settings
from src.rcrag.infrastructure.factory import build_historian, init_observability

# Assume previous phases already defined routers and health endpoints elsewhere


def create_app() -> FastAPI:
    app = FastAPI(title="RCRAG Service")

    settings = Settings()

    # Initialize observability
    init_observability(app, settings)

    # Hook to build historian if needed by the application layer
    # The existing application wiring should retrieve the historian via factory
    build_historian(settings)  # side effect: readiness; adapter returned if needed elsewhere

    # Add /metrics endpoint if prometheus enabled handled by init_observability

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app


app = create_app()

# Configure logging to include trace context placeholders (if not already in logging config)
logging.getLogger("uvicorn").handlers  # touch to ensure handlers exist
