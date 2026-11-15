"""
API Route Handlers.
Clean separation of HTTP endpoint declarations from business logic services.
"""

from fastapi import APIRouter, status

from app.schemas.health import HealthResponse
from app.schemas.task import TaskIntentRequest, TaskIntentResponse
from app.services.groq_service import groq_service

router = APIRouter(tags=["System & Intent"])


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Health Check",
    description="Returns the health status and application identifier.",
)
async def health_check() -> HealthResponse:
    """
    Standard health check endpoint required by the architecture specification.
    """
    return HealthResponse(
        status="healthy",
        application="CLI Agent AI"
    )


@router.post(
    "/intent/preview",
    response_model=TaskIntentResponse,
    status_code=status.HTTP_200_OK,
    summary="Task Intent Preview",
    description="Analyzes natural language prompt and previews parsed CLI intent without execution.",
)
async def preview_intent(payload: TaskIntentRequest) -> TaskIntentResponse:
    """
    Previews how the Groq service interprets the natural language instructions.
    """
    return groq_service.parse_task_intent(payload.prompt)

