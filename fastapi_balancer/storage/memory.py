import asyncio
from fastapi_balancer.storage.base import AbstractStorage


class MemoryStorage(AbstractStorage):
    def __init__(self) -> None:
        self._capacity: dict[str, int] = {}
        self._active: dict[str, int] = {}
        self._health: dict[str, bool] = {}
        self._lock = asyncio.Lock()
        self._probe_locks: dict[str, bool] = {}

    async def get_capacity(self, endpoint: str) -> int:
        return self._capacity.get(endpoint, 0)

    async def set_capacity(self, endpoint: str, value: int) -> None:
        self._capacity[endpoint] = value

    async def increment_active(self, endpoint: str) -> int:
        async with self._lock:
            self._active[endpoint] = self._active.get(endpoint, 0) + 1
            return self._active[endpoint]

    async def decrement_active(self, endpoint: str) -> int:
        async with self._lock:
            current = self._active.get(endpoint, 0)
            self._active[endpoint] = max(0, current - 1)
            return self._active[endpoint]

    async def get_active(self, endpoint: str) -> int:
        return self._active.get(endpoint, 0)

    async def get_health(self, backend: str) -> bool:
        return self._health.get(backend, True)

    async def set_health(self, backend: str, value: bool) -> None:
        self._health[backend] = value

    async def acquire_probe_lock(self, endpoint: str, ttl_seconds: int = 60) -> bool:
        async with self._lock:
            if self._probe_locks.get(endpoint):
                return False
            self._probe_locks[endpoint] = True
            return True

    async def release_probe_lock(self, endpoint: str) -> None:
        self._probe_locks.pop(endpoint, None)

    async def close(self) -> None:
        pass
