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


@pytest.fixture
def ready_session():
    session_module.reset()
    session_module.update(
        status="ready",
        job_id="test-job-001",
        source_path="/fake/video.mp4",
        source_info={"fps": 25, "duration_s": 10, "width": 1920, "height": 1080},
    )
    yield
