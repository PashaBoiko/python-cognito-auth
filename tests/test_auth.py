from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.dependencies import get_current_user, get_db_session
from app.main import create_app


@pytest.fixture()
def app():
    application = create_app()

    async def override_db_session():
        yield AsyncMock()

    application.dependency_overrides[get_db_session] = override_db_session
    return application


@pytest.fixture()
def client(app):
    return TestClient(app)


def test_root_returns_service_name(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Python Auth Microservice"}


def test_auth_exchange_missing_body(client):
    response = client.post("/api/v1/auth")
    assert response.status_code == 422


def test_validate_without_token_returns_401(client):
    response = client.post("/api/v1/auth/validate")
    assert response.status_code == 401


def test_logout_without_token_returns_401(client):
    response = client.post("/api/v1/auth/logout")
    assert response.status_code == 401


def test_validate_with_valid_token(app, client):
    fake_user = SimpleNamespace(
        id=uuid4(),
        email="test@example.com",
        cognito_sub="cognito-sub-123",
        role=SimpleNamespace(name="user"),
    )

    app.dependency_overrides[get_current_user] = lambda: fake_user

    response = client.post("/api/v1/auth/validate")
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "test@example.com"
    assert data["role"] == "user"
