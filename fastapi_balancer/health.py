import asyncio
import logging
from typing import Any

import httpx

from fastapi_balancer.storage.base import AbstractStorage

logger = logging.getLogger(__name__)


class HealthChecker:
    def __init__(self, storage: AbstractStorage, app: Any) -> None:
        self._storage = storage
        self._app = app
        self._task: asyncio.Task | None = None

    def start(self, backends: list[str], health_endpoint: str, interval: int) -> None:
        self._task = asyncio.create_task(
            self._run(backends, health_endpoint, interval)
        )

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _run(self, backends: list[str], health_endpoint: str, interval: int) -> None:
        while True:
            for backend in backends:
                await self._check(backend, health_endpoint)
            await asyncio.sleep(interval)

    async def _check(self, backend: str, health_endpoint: str) -> None:
        url = backend.rstrip("/") + health_endpoint
        was_healthy = await self._storage.get_health(backend)
        try:
            transport = httpx.ASGITransport(app=self._app)
            async with httpx.AsyncClient(transport=transport, base_url=backend) as client:
                response = await client.get(health_endpoint, timeout=5.0)
            is_healthy = response.status_code < 400
        except Exception:
            is_healthy = False

        if was_healthy != is_healthy:
            await self._storage.set_health(backend, is_healthy)
            status = "recovered" if is_healthy else "unhealthy"
            logger.warning("backend %s is now %s", backend, status)
