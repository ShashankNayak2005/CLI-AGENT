"""
CLI Agent AI - FastAPI Application Entrypoint.
Centralized exception handling, logging, CORS, and route registration.
"""

import logging
import sys
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.agent import router as agent_router
from app.api.chat import router as chat_router
from app.api.routes import router as api_router
from app.api.tasks import router as tasks_router
from app.config import get_settings
from app.models.database import init_db
from app.schemas.health import HealthResponse
from app.security.sanitizer import SecurityException

# -----------------------------------------------------------------------------
# Structured Logging Configuration
# -----------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("cli_agent.main")


# -----------------------------------------------------------------------------
# Application Lifespan
# -----------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()
    logger.info("Starting up %s (Version %s, Env: %s)",
                settings.app_name, settings.app_version, settings.app_env)
    # Initialize SQLite database schema
    init_db()
    yield
    logger.info("Shutting down %s", settings.app_name)


# -----------------------------------------------------------------------------
# FastAPI App Initialization
# -----------------------------------------------------------------------------
settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="An AI-powered conversational platform that converts natural-language instructions into controlled CLI executions.",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    lifespan=lifespan,
)

# -----------------------------------------------------------------------------
# Restrictive CORS Configuration
# -----------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "Accept"],
)


# -----------------------------------------------------------------------------
# Centralized Exception Handling
# -----------------------------------------------------------------------------
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Handles standard HTTP errors cleanly without leaking sensitive details."""
    logger.warning("HTTP Exception on %s: %s", request.url.path, exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "status_code": exc.status_code,
            "message": exc.detail,
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handles Pydantic validation failures with structured error output."""
    errors = [
        {"field": ".".join(str(loc) for loc in err.get("loc", [])), "message": err.get("msg")}
        for err in exc.errors()
    ]
    logger.warning("Validation error on %s: %s", request.url.path, errors)
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": True,
            "status_code": 422,
            "message": "Input validation failed.",
            "details": errors,
        },
    )


@app.exception_handler(SecurityException)
async def security_exception_handler(request: Request, exc: SecurityException) -> JSONResponse:
    """Catches violations of command or security policies."""
    logger.error("Security violation on %s: %s", request.url.path, str(exc))
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error": True,
            "status_code": 400,
            "message": "Security policy violation: Request rejected.",
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Safely captures unhandled exceptions.
    Never exposes internal tracebacks or environment variables to the client.
    """
    logger.error("Unhandled server exception on %s: %s", request.url.path, str(exc), exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": True,
            "status_code": 500,
            "message": "An internal server error occurred. Please contact the administrator.",
        },
    )


# -----------------------------------------------------------------------------
# Route Registration
# -----------------------------------------------------------------------------
# Mount API endpoints under /api
app.include_router(api_router, prefix="/api")
app.include_router(chat_router, prefix="/api")
app.include_router(tasks_router, prefix="/api")
app.include_router(agent_router, prefix="/api")

# Also provide direct root health check convenience
@app.get("/health", response_model=HealthResponse, include_in_schema=False)
async def root_health() -> HealthResponse:
    return HealthResponse(status="healthy", application="CLI Agent AI")

