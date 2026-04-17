import asyncio
import pytest
from fastapi_balancer.limiter import Limiter, QueueTimeoutError
from fastapi_balancer.storage.memory import MemoryStorage


@pytest.fixture
def storage():
    return MemoryStorage()


@pytest.fixture
def limiter(storage):
    return Limiter(storage)


async def test_acquire_within_capacity(storage, limiter):
    await storage.set_capacity("/predict", 5)
    await limiter.acquire("/predict", queue_timeout=5.0)
    assert await storage.get_active("/predict") == 1


async def test_release_decrements(storage, limiter):
    await storage.set_capacity("/predict", 5)
    await limiter.acquire("/predict", queue_timeout=5.0)
    await limiter.release("/predict")
    assert await storage.get_active("/predict") == 0


async def test_queue_timeout_when_full(storage, limiter):
    await storage.set_capacity("/predict", 1)
    await limiter.acquire("/predict", queue_timeout=5.0)
    # second acquire should timeout quickly
    with pytest.raises(QueueTimeoutError):
        await limiter.acquire("/predict", queue_timeout=0.1)


async def test_waiting_request_proceeds_after_release(storage, limiter):
    await storage.set_capacity("/predict", 1)
    await limiter.acquire("/predict", queue_timeout=5.0)

    released = asyncio.Event()

    async def holder():
        await asyncio.sleep(0.05)
        await limiter.release("/predict")
        released.set()

    asyncio.create_task(holder())
    # this should wait and then succeed
    await limiter.acquire("/predict", queue_timeout=2.0)
    assert released.is_set()
    await limiter.release("/predict")
