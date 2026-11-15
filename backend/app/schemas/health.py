"""
Health check schema.
"""

from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):
    """
    Standard health check response schema.
    """
    status: str = "healthy"
    application: str = "CLI Agent AI"

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "healthy",
                "application": "CLI Agent AI"
            }
        }
    )

