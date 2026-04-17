import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from fastapi_balancer.limiter import Limiter, QueueTimeoutError
from fastapi_balancer.router import AbstractRouter
from fastapi_balancer.storage.base import AbstractStorage

logger = logging.getLogger(__name__)


class BalancerMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        *,
        watched_endpoints: list[str],
        backends: list[str],
        router: AbstractRouter,
        limiter: Limiter,
        storage: AbstractStorage,
        queue_timeout: float,
        endpoint_queue_timeouts: dict[str, float] | None = None,
    ) -> None:
        super().__init__(app)
        self._watched = set(watched_endpoints)
        self._backends = backends
        self._router = router
        self._limiter = limiter
        self._storage = storage
        self._queue_timeout = queue_timeout
        self._endpoint_queue_timeouts = endpoint_queue_timeouts or {}

    def _resolve_timeout(self, path: str) -> float:
        return self._endpoint_queue_timeouts.get(path, self._queue_timeout)

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path

        if path not in self._watched:
            return await call_next(request)

        backend = await self._router.select(self._backends, path)
        if backend and not await self._storage.get_health(backend):
            return JSONResponse({"error": "service unavailable"}, status_code=503)

        try:
            await self._limiter.acquire(path, self._resolve_timeout(path))
        except QueueTimeoutError:
            logger.warning("queue timeout for %s", path)
            return JSONResponse({"error": "request timed out in queue"}, status_code=504)

        try:
            response = await call_next(request)
        finally:
            await self._limiter.release(path)

        return response
