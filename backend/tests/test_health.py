"""
Tests for API health check endpoint.
"""

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_api_health_endpoint():
    """
    Verify GET /api/health returns 200 OK with expected JSON structure:
    {
      "status": "healthy",
      "application": "CLI Agent AI"
    }
    """
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["application"] == "CLI Agent AI"


def test_root_health_endpoint():
    """Verify convenience /health route functions identically."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "application": "CLI Agent AI"
    }

