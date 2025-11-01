import logging

from fastapi import FastAPI

from src.rcrag.infrastructure.config import Settings
from src.rcrag.infrastructure.factory import build_historian, init_observability
from src.rcrag.api.routes import router as api_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="RCRAG Service",
        description="Reality-Checked RAG service with institutional memory and trust policies",
        version="1.0.0"
    )

    settings = Settings()

    # Initialize observability
    init_observability(app, settings)

    # Hook to build historian if needed by the application layer
    # The existing application wiring should retrieve the historian via factory
    build_historian(settings)  # side effect: readiness; adapter returned if needed elsewhere

    # Add API routes
    app.include_router(api_router)

    # Health endpoint
    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app


app = create_app()

# Configure logging to include trace context placeholders (if not already in logging config)
logging.getLogger("uvicorn").handlers  # touch to ensure handlers exist
