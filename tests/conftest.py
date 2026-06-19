import pytest
from httpx import AsyncClient, ASGITransport

import app.session as session_module


@pytest.fixture(autouse=True)
def reset_session():
    """Reset session state before every test."""
    session_module.reset()
    yield
    session_module.reset()


@pytest.fixture
def client():
    """Synchronous TestClient for FastAPI — used for non-async tests."""
    from fastapi.testclient import TestClient
    from app.main import create_app
    app = create_app()
    with TestClient(app) as c:
        yield c


@pytest.fixture
async def async_client():
    """AsyncClient for async endpoint tests."""
    from app.main import create_app
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
