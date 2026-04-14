"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .models.schemas import HealthResponse
from .routers import cr_router
from .services.ai_service import AIService
from .services.cr_service import CRService
import uvicorn

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup and shutdown."""
    # Startup
    logger.info("Starting AI Code Review Service...")
    settings = get_settings()
    logger.info(f"GitLab URL: {settings.gitlab_url}")
    logger.info(f"LLM Model: {settings.llm_model}")

    # Initialize services
    try:
        cr_service = CRService(settings)
        # Store in app state for health check
        app.state.cr_service = cr_service
        logger.info("Services initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize services: {e}")
        raise

    yield

    # Shutdown
    logger.info("Shutting down AI Code Review Service...")


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        description="AI-powered code review service for GitLab merge requests",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(cr_router)

    # Health check endpoint
    @app.get("/health", response_model=HealthResponse)
    async def health_check():
        """Health check endpoint."""
        cr_service = getattr(app.state, "cr_service", None)

        llm_connected = False

        if cr_service:
            try:
                llm_connected = cr_service.ai_service.health_check()
            except Exception:
                pass

        return HealthResponse(
            status="healthy" if llm_connected else "degraded",
            version="0.1.0",
            llm_connected=llm_connected,
        )

    # Root endpoint
    @app.get("/")
    async def root():
        """Root endpoint."""
        return {
            "name": settings.app_name,
            "version": "0.1.0",
            "docs": "/docs",
            "health": "/health",
        }

    return app


# Create app instance
app = create_app()


if __name__ == "__main__":

    settings = get_settings()
    uvicorn.run(
        "ai_cr_service.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
