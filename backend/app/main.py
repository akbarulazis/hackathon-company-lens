"""FastAPI application factory with lifespan events.

The application validates all required secrets at startup and refuses
to start if any are missing. Uses async-only operations throughout.
"""

import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from redis.asyncio import Redis

from app.auth.router import router as auth_router
from app.charts.router import router as charts_router
from app.chatbot.router import router as chatbot_router
from app.companies.router import router as companies_router
from app.comparison.router import router as comparison_router
from app.config import Settings, get_settings
from app.database import create_engine
from app.documents.router import router as documents_router
from app.graph.router import router as graph_router
from app.notifications.manager import init_notification_manager
from app.notifications.router import router as ws_router
from app.portfolio.router import router as portfolio_router
from app.workspaces.router import router as workspaces_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: validate config and manage resources."""
    settings: Settings = app.state.settings
    engine = create_engine(settings)

    # Initialize Redis connection for notifications
    redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    manager = init_notification_manager(redis)

    app.state.engine = engine
    app.state.redis = redis
    app.state.notification_manager = manager
    logger.info(
        "Company Lens started (environment=%s, debug=%s)",
        settings.ENVIRONMENT,
        settings.DEBUG,
    )

    yield

    # Shutdown: close Redis and dispose engine
    await redis.aclose()
    await engine.dispose()
    logger.info("Company Lens shut down cleanly.")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Validates required secrets at startup. If any required secret
    is missing or empty, raises a ValidationError which prevents
    the application from starting.
    """
    # This call validates all required secrets. If any are missing,
    # a ValidationError is raised and the app refuses to start.
    settings = get_settings()

    app = FastAPI(
        title=settings.APP_NAME,
        docs_url="/api/docs" if not settings.is_production else None,
        redoc_url="/api/redoc" if not settings.is_production else None,
        openapi_url="/api/openapi.json" if not settings.is_production else None,
        debug=settings.DEBUG and not settings.is_production,
        lifespan=lifespan,
    )

    app.state.settings = settings

    # Include WebSocket router
    app.include_router(ws_router)

    # Include auth router
    app.include_router(auth_router)

    # Include companies router
    app.include_router(companies_router)

    # Include workspaces router
    app.include_router(workspaces_router)

    # Include comparison router
    app.include_router(comparison_router)

    # Include chatbot router
    app.include_router(chatbot_router)

    # Include documents router
    app.include_router(documents_router)

    # Include portfolio router
    app.include_router(portfolio_router)

    # Include graph router
    app.include_router(graph_router)

    # Include charts router
    app.include_router(charts_router)

    return app


# Module-level app instance for uvicorn
app = create_app()
