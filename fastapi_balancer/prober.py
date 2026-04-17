import asyncio
import logging
import statistics
import time
from datetime import datetime, timezone

import httpx

logger = logging.getLogger(__name__)

from fastapi_balancer.models import EndpointProbeConfig, ProbeResult
from fastapi_balancer.storage.base import AbstractStorage


class Prober:
    def __init__(
        self,
        storage: AbstractStorage,
        http_client: httpx.AsyncClient,
        error_threshold: float = 0.05,
        latency_threshold_ms: float = 2000.0,
    ) -> None:
        self._storage = storage
        self._client = http_client
        self._error_threshold = error_threshold
        self._latency_threshold_ms = latency_threshold_ms

    async def probe(
        self,
        base_url: str,
        endpoint: str,
        probe_config: EndpointProbeConfig,
        force: bool = False,
        client: httpx.AsyncClient | None = None,
    ) -> ProbeResult:
        # if another worker already probed, reuse the result
        if not force:
            existing = await self._storage.get_capacity(endpoint)
            if existing > 0:
                logger.info(
                    "skipping probe for %s — capacity already set to %d by another worker",
                    endpoint,
                    existing,
                )
                return ProbeResult(
                    backend_url=base_url,
                    endpoint=endpoint,
                    max_concurrency=existing,
                    p99_latency_ms=0.0,
                    rps=0.0,
                    probed_at=datetime.now(timezone.utc),
                )

        # acquire distributed lock so only one worker runs the probe
        acquired = await self._storage.acquire_probe_lock(endpoint)
        if not acquired:
            # another worker is currently probing — wait and then read its result
            logger.info(
                "probe lock busy for %s — waiting for another worker to finish",
                endpoint,
            )
            for _ in range(30):
                await asyncio.sleep(1)
                capacity = await self._storage.get_capacity(endpoint)
                if capacity > 0:
                    logger.info(
                        "got capacity %d for %s from another worker", capacity, endpoint
                    )
                    return ProbeResult(
                        backend_url=base_url,
                        endpoint=endpoint,
                        max_concurrency=capacity,
                        p99_latency_ms=0.0,
                        rps=0.0,
                        probed_at=datetime.now(timezone.utc),
                    )
            logger.warning(
                "timed out waiting for probe result for %s, probing independently",
                endpoint,
            )

        active_client = client or self._client
        last_good_concurrency = 1
        last_good_p99 = 0.0
        last_good_rps = 0.0

        levels = self._concurrency_levels()
        first_bad: int | None = None

        for concurrency in levels:
            error_rate, p99, rps = await self._measure(
                base_url, endpoint, probe_config, concurrency, active_client
            )
            logger.info(
                "[probe] %s concurrency=%d → error_rate=%.1f%% p99=%.0fms rps=%.1f",
                endpoint,
                concurrency,
                error_rate * 100,
                p99,
                rps,
            )
            if error_rate > self._error_threshold:
                logger.warning(
                    "[probe] %s stopped at concurrency=%d — error_rate=%.1f%% exceeds threshold=%.1f%%",
                    endpoint,
                    concurrency,
                    error_rate * 100,
                    self._error_threshold * 100,
                )
                first_bad = concurrency
                break
            if p99 > self._latency_threshold_ms:
                logger.warning(
                    "[probe] %s stopped at concurrency=%d — p99=%.0fms exceeds threshold=%.0fms",
                    endpoint,
                    concurrency,
                    p99,
                    self._latency_threshold_ms,
                )
                first_bad = concurrency
                break
            last_good_concurrency = concurrency
            last_good_p99 = p99
            last_good_rps = rps

        # binary search refinement between last_good and first_bad
        if first_bad is not None and first_bad - last_good_concurrency > 2:
            lo, hi = last_good_concurrency, first_bad
            while hi - lo > 1:
                mid = (lo + hi) // 2
                error_rate, p99, rps = await self._measure(
                    base_url, endpoint, probe_config, mid, active_client
                )
                if (
                    error_rate > self._error_threshold
                    or p99 > self._latency_threshold_ms
                ):
                    hi = mid
                else:
                    lo = mid
                    last_good_concurrency = mid
                    last_good_p99 = p99
                    last_good_rps = rps

        await self._storage.set_capacity(endpoint, last_good_concurrency)
        await self._storage.release_probe_lock(endpoint)

        return ProbeResult(
            backend_url=base_url,
            endpoint=endpoint,
            max_concurrency=last_good_concurrency,
            p99_latency_ms=last_good_p99,
            rps=last_good_rps,
            probed_at=datetime.now(timezone.utc),
        )

    async def _measure(
        self,
        base_url: str,
        endpoint: str,
        probe_config: EndpointProbeConfig,
        concurrency: int,
        client: httpx.AsyncClient | None = None,
    ) -> tuple[float, float, float]:
        url = base_url.rstrip("/") + endpoint
        active_client = client or self._client
        tasks = [
            self._single_request(
                url,
                probe_config,
                active_client,
                log_error_body=(i == 0 and concurrency == 1),
            )
            for i in range(concurrency)
        ]
        t_start = time.perf_counter()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        elapsed = time.perf_counter() - t_start

        latencies: list[float] = []
        errors = 0
        for r in results:
            if isinstance(r, Exception):
                errors += 1
            else:
                status, latency_ms = r
                if status >= 400:
                    errors += 1
                else:
                    latencies.append(latency_ms)

        error_rate = errors / concurrency
        p99 = (
            statistics.quantiles(latencies, n=100)[98]
            if len(latencies) >= 2
            else (latencies[0] if latencies else self._latency_threshold_ms + 1)
        )
        rps = concurrency / elapsed if elapsed > 0 else 0.0

        return error_rate, p99, rps

    async def _single_request(
        self,
        url: str,
        probe_config: EndpointProbeConfig,
        client: httpx.AsyncClient | None = None,
        log_error_body: bool = False,
    ) -> tuple[int, float]:
        active_client = client or self._client
        t0 = time.perf_counter()
        response = await active_client.request(
            method=probe_config.method,
            url=url,
            headers=probe_config.headers,
            json=probe_config.body,
        )
        latency_ms = (time.perf_counter() - t0) * 1000
        if log_error_body and response.status_code >= 400:
            try:
                body = response.text[:500]
            except Exception:
                body = "<unreadable>"
            logger.warning(
                "[probe] error response status=%d body=%s", response.status_code, body
            )
        return response.status_code, latency_ms

    def _concurrency_levels(self) -> list[int]:
        levels = []
        c = 1
        while c <= 1024:
            levels.append(c)
            c *= 2
        return levels
