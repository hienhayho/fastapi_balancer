import asyncio
from collections import deque

from fastapi_balancer.storage.base import AbstractStorage


class QueueTimeoutError(Exception):
    pass


class Limiter:
    def __init__(self, storage: AbstractStorage) -> None:
        self._storage = storage
        self._waiters: dict[str, deque[asyncio.Future]] = {}

    def _get_waiters(self, endpoint: str) -> deque[asyncio.Future]:
        if endpoint not in self._waiters:
            self._waiters[endpoint] = deque()
        return self._waiters[endpoint]

    async def acquire(self, endpoint: str, queue_timeout: float) -> None:
        capacity = await self._storage.get_capacity(endpoint)
        active = await self._storage.get_active(endpoint)

        if capacity == 0 or active < capacity:
            await self._storage.increment_active(endpoint)
            return

        # slot full — enqueue a Future and wait for release() to resolve it
        loop = asyncio.get_event_loop()
        fut: asyncio.Future = loop.create_future()
        waiters = self._get_waiters(endpoint)
        waiters.append(fut)
        try:
            await asyncio.wait_for(asyncio.shield(fut), timeout=queue_timeout)
        except asyncio.TimeoutError:
            try:
                waiters.remove(fut)
            except ValueError:
                pass  # release() already popped it — decrement the slot it granted
            raise QueueTimeoutError(f"Request to {endpoint} timed out in queue")

    async def release(self, endpoint: str) -> None:
        await self._storage.decrement_active(endpoint)
        waiters = self._get_waiters(endpoint)
        # wake the longest-waiting request (FIFO)
        while waiters:
            fut = waiters.popleft()
            if not fut.done():
                fut.set_result(None)
                await self._storage.increment_active(endpoint)
                return

    async def get_queue_size(self, endpoint: str) -> int:
        return len(self._get_waiters(endpoint))
