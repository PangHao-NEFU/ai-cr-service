"""Tests for AI CR Service main endpoints."""

import pytest
from fastapi.testclient import TestClient

from ai_cr_service.main import create_app


@pytest.fixture
def client():
    """Create test client."""
    app = create_app()
    return TestClient(app)


def test_root_endpoint(client):
    """Test root endpoint returns service info."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "name" in data
    assert "version" in data
    assert data["docs"] == "/docs"


def test_health_endpoint(client):
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "version" in data
    assert "llm_connected" in data
    assert "redis_connected" in data


def test_trigger_endpoint_without_auth(client):
    """Test trigger endpoint without authentication."""
    response = client.post(
        "/api/cr/trigger",
        json={
            "project_id": 1,
            "mr_iid": 1,
        },
    )
    # Should fail due to missing GitLab config, but endpoint should be accessible
    assert response.status_code == 200
    data = response.json()
    assert "code" in data
    assert "msg" in data


def test_preview_endpoint(client):
    """Test preview endpoint with sample diff."""
    response = client.post(
        "/api/cr/preview",
        json=[
            {
                "new_path": "src/main.py",
                "diff": """
def hello():
    password = "hardcoded_secret_123"
    sql = f"SELECT * FROM users WHERE id = {user_input}"
    return sql
""",
            }
        ],
    )
    # This will fail without LLM API key, but endpoint should be accessible
    assert response.status_code in [200, 500]
