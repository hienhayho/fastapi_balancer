import pytest
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport

from fastapi_balancer import Balancer, BalancerConfig
from fastapi_balancer.models import EndpointProbeConfig


def make_app():
    import asyncio
    app = FastAPI()

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.post("/predict")
    async def predict():
        await asyncio.sleep(0.01)
        return {"result": "ok"}

    return app


async def test_non_watched_endpoint_passes_through():
    app = make_app()
    cfg = BalancerConfig(probe_on_startup=False)
    balancer = Balancer(config=cfg)
    balancer.wrap(app, endpoints=["/predict"])

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/health")
        assert resp.status_code == 200


async def test_watched_endpoint_admitted():
    app = make_app()
    cfg = BalancerConfig(
        probe_on_startup=False,
        endpoints={"/predict": EndpointProbeConfig(method="POST")},
    )
    balancer = Balancer(config=cfg)
    balancer.wrap(app, endpoints=["/predict"])

    # manually set capacity so middleware admits
    from fastapi_balancer.storage.memory import MemoryStorage
    # re-wrap with known storage
    app2 = make_app()
    storage = MemoryStorage()
    await storage.set_capacity("/predict", 10)

    from fastapi_balancer.limiter import Limiter
    from fastapi_balancer.router import get_router
    from fastapi_balancer.middleware import BalancerMiddleware

    router = get_router("round-robin", storage)
    limiter = Limiter(storage)
    app2.add_middleware(
        BalancerMiddleware,
        watched_endpoints=["/predict"],
        backends=["http://localhost"],
        router=router,
        limiter=limiter,
        storage=storage,
        queue_timeout=5.0,
    )

    async with AsyncClient(transport=ASGITransport(app=app2), base_url="http://test") as client:
        resp = await client.post("/predict")
        assert resp.status_code == 200


async def test_stats_endpoint():
    app = make_app()
    cfg = BalancerConfig(probe_on_startup=False)
    balancer = Balancer(config=cfg)
    balancer.wrap(app, endpoints=["/predict"])

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/balancer/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "endpoints" in data
        assert "/predict" in data["endpoints"]
