import pytest
import httpx
from fastapi_balancer.prober import Prober
from fastapi_balancer.models import EndpointProbeConfig
from fastapi_balancer.storage.memory import MemoryStorage


@pytest.fixture
def storage():
    return MemoryStorage()


async def test_probe_sets_capacity(slow_app, storage):
    transport = httpx.ASGITransport(app=slow_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        prober = Prober(storage, client, error_threshold=0.05, latency_threshold_ms=5000.0)
        probe_cfg = EndpointProbeConfig(method="POST", body={})
        result = await prober.probe("http://test", "/predict", probe_cfg)

    assert result.max_concurrency >= 1
    assert await storage.get_capacity("/predict") == result.max_concurrency
