import pytest
from fastapi_balancer.storage.memory import MemoryStorage


@pytest.fixture
def storage():
    return MemoryStorage()


async def test_capacity(storage):
    await storage.set_capacity("/predict", 10)
    assert await storage.get_capacity("/predict") == 10


async def test_active_increment_decrement(storage):
    await storage.set_capacity("/predict", 5)
    v1 = await storage.increment_active("/predict")
    v2 = await storage.increment_active("/predict")
    assert v1 == 1
    assert v2 == 2
    v3 = await storage.decrement_active("/predict")
    assert v3 == 1


async def test_active_no_negative(storage):
    result = await storage.decrement_active("/predict")
    assert result == 0


async def test_health_defaults_true(storage):
    assert await storage.get_health("http://localhost") is True


async def test_health_set(storage):
    await storage.set_health("http://localhost", False)
    assert await storage.get_health("http://localhost") is False
