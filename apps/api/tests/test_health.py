from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from novoya_api.db import get_session
from novoya_api.main import create_app


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def test_health_is_ok(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_db_health_returns_503_when_database_fails(app, client):
    class BrokenSession:
        async def execute(self, *args, **kwargs):
            raise ConnectionError("database down")

    async def broken_session():
        yield BrokenSession()

    app.dependency_overrides[get_session] = broken_session
    response = await client.get("/health/db")
    assert response.status_code == 503
    assert response.json() == {"status": "error"}
