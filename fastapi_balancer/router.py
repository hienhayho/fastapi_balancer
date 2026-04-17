import itertools
from abc import ABC, abstractmethod

from fastapi_balancer.models import RoutingStrategy
from fastapi_balancer.storage.base import AbstractStorage


class AbstractRouter(ABC):
    @abstractmethod
    async def select(self, backends: list[str], endpoint: str) -> str | None: ...


class RoundRobinRouter(AbstractRouter):
    def __init__(self) -> None:
        self._counters: dict[str, itertools.cycle] = {}
        self._lists: dict[str, list[str]] = {}

    async def select(self, backends: list[str], endpoint: str) -> str | None:
        if not backends:
            return None
        key = ",".join(backends)
        if key not in self._counters or self._lists.get(endpoint) != backends:
            self._lists[endpoint] = backends
            self._counters[endpoint] = itertools.cycle(backends)
        return next(self._counters[endpoint])


class LeastConnectionsRouter(AbstractRouter):
    def __init__(self, storage: AbstractStorage) -> None:
        self._storage = storage

    async def select(self, backends: list[str], endpoint: str) -> str | None:
        if not backends:
            return None
        counts = [(await self._storage.get_active(f"{b}{endpoint}"), b) for b in backends]
        return min(counts, key=lambda x: x[0])[1]


class WeightedRouter(AbstractRouter):
    def __init__(self, storage: AbstractStorage) -> None:
        self._storage = storage

    async def select(self, backends: list[str], endpoint: str) -> str | None:
        if not backends:
            return None
        # pick backend with most remaining capacity (capacity - active)
        scores = []
        for b in backends:
            cap = await self._storage.get_capacity(endpoint)
            active = await self._storage.get_active(f"{b}{endpoint}")
            scores.append((cap - active, b))
        return max(scores, key=lambda x: x[0])[1]


def get_router(strategy: RoutingStrategy, storage: AbstractStorage) -> AbstractRouter:
    if strategy == RoutingStrategy.LEAST_CONNECTIONS:
        return LeastConnectionsRouter(storage)
    if strategy == RoutingStrategy.WEIGHTED:
        return WeightedRouter(storage)
    return RoundRobinRouter()
