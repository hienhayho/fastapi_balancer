import asyncio
import pytest
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def slow_app():
    app = FastAPI()

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.post("/predict")
    async def predict():
        await asyncio.sleep(0.05)
        return {"result": "ok"}

    return app


@pytest.fixture
async def async_client(slow_app):
    async with AsyncClient(transport=ASGITransport(app=slow_app), base_url="http://test") as client:
        yield client
