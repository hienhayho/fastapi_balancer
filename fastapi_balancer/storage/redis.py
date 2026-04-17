from redis.asyncio import Redis, ConnectionPool

from .base import AbstractStorage


class RedisStorage(AbstractStorage):
    def __init__(self, url: str) -> None:
        pool = ConnectionPool.from_url(url, decode_responses=True)
        self._redis: Redis = Redis(connection_pool=pool)

    async def get_capacity(self, endpoint: str) -> int:
        val = await self._redis.hget("balancer:capacity", endpoint)
        return int(val) if val is not None else 0

    async def set_capacity(self, endpoint: str, value: int) -> None:
        await self._redis.hset("balancer:capacity", endpoint, value)

    async def increment_active(self, endpoint: str) -> int:
        return int(await self._redis.incr(f"balancer:active:{endpoint}"))

    async def decrement_active(self, endpoint: str) -> int:
        result = await self._redis.decr(f"balancer:active:{endpoint}")
        val = int(result)
        if val < 0:
            await self._redis.set(f"balancer:active:{endpoint}", 0)
            return 0
        return val

    async def get_active(self, endpoint: str) -> int:
        val = await self._redis.get(f"balancer:active:{endpoint}")
        return int(val) if val is not None else 0

    async def get_health(self, backend: str) -> bool:
        val = await self._redis.hget("balancer:health", backend)
        return val != "0" if val is not None else True

    async def set_health(self, backend: str, value: bool) -> None:
        await self._redis.hset("balancer:health", backend, "1" if value else "0")

    async def acquire_probe_lock(self, endpoint: str, ttl_seconds: int = 60) -> bool:
        key = f"balancer:probe_lock:{endpoint}"
        result = await self._redis.set(key, "1", nx=True, ex=ttl_seconds)
        return result is not None

    async def release_probe_lock(self, endpoint: str) -> None:
        await self._redis.delete(f"balancer:probe_lock:{endpoint}")

    async def close(self) -> None:
        await self._redis.aclose()
