import asyncio

from .storage.base import AbstractStorage


class QueueTimeoutError(Exception):
    pass


class Limiter:
    def __init__(self, storage: AbstractStorage) -> None:
        self._storage = storage
        # per-endpoint asyncio.Event used to notify waiting requests
        self._events: dict[str, asyncio.Event] = {}

    def _get_event(self, endpoint: str) -> asyncio.Event:
        if endpoint not in self._events:
            self._events[endpoint] = asyncio.Event()
        return self._events[endpoint]

    async def acquire(self, endpoint: str, queue_timeout: float) -> None:
        deadline = asyncio.get_event_loop().time() + queue_timeout
        while True:
            capacity = await self._storage.get_capacity(endpoint)
            active = await self._storage.get_active(endpoint)

            if capacity == 0 or active < capacity:
                await self._storage.increment_active(endpoint)
                return

            # slot full — wait for a release notification
            event = self._get_event(endpoint)
            event.clear()
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                raise QueueTimeoutError(f"Request to {endpoint} timed out in queue")
            try:
                await asyncio.wait_for(event.wait(), timeout=remaining)
            except asyncio.TimeoutError:
                raise QueueTimeoutError(f"Request to {endpoint} timed out in queue")

    async def release(self, endpoint: str) -> None:
        await self._storage.decrement_active(endpoint)
        # notify one waiting coroutine
        event = self._get_event(endpoint)
        event.set()

    async def get_queue_size(self, endpoint: str) -> int:
        capacity = await self._storage.get_capacity(endpoint)
        active = await self._storage.get_active(endpoint)
        return max(0, active - capacity)
