import asyncio
import pytest
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport

from fastapi_balancer import Balancer, BalancerConfig
from fastapi_balancer.models import EndpointProbeConfig


def make_app():
    app = FastAPI()

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.post("/predict")
    async def predict():
        await asyncio.sleep(0.02)
        return {"result": "ok"}

    return app


async def test_all_requests_handled_under_load():
    app = make_app()
    cfg = BalancerConfig(
        probe_on_startup=False,
        queue_timeout=10.0,
    )
    balancer = Balancer(config=cfg)
    balancer.wrap(app, endpoints=["/predict"])

    # manually set capacity
    from fastapi_balancer.storage.memory import MemoryStorage
    app2 = make_app()
    storage = MemoryStorage()
    await storage.set_capacity("/predict", 5)

    from fastapi_balancer.limiter import Limiter
    from fastapi_balancer.router import get_router
    from fastapi_balancer.middleware import BalancerMiddleware

    app2.add_middleware(
        BalancerMiddleware,
        watched_endpoints=["/predict"],
        backends=["http://localhost"],
        router=get_router("round-robin", storage),
        limiter=Limiter(storage),
        storage=storage,
        queue_timeout=10.0,
    )

    async with AsyncClient(transport=ASGITransport(app=app2), base_url="http://test") as client:
        tasks = [client.post("/predict") for _ in range(20)]
        responses = await asyncio.gather(*tasks)

    statuses = [r.status_code for r in responses]
    assert all(s == 200 for s in statuses), f"unexpected statuses: {statuses}"
