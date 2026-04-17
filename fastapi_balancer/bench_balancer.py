import asyncio
import logging
from pathlib import Path

import httpx
import yaml

from .config import BalancerConfig
from .models import EndpointProbeConfig
from .prober import Prober
from .storage.memory import MemoryStorage

logger = logging.getLogger(__name__)


class BenchBalancer:
    """
    Standalone benchmarking tool — probe a live API directly by base URL,
    then export the measured config as a YAML file for use with Balancer.

    Usage:
        asyncio.run(
            BenchBalancer(
                base_url="http://localhost:8005",
                endpoints={
                    "/ai_score": EndpointProbeConfig(
                        method="POST",
                        headers={"Authorization": "Bearer token"},
                        body={"inputs": [...]},
                    )
                },
                latency_threshold_ms=80000,
                storage="redis://localhost:6379",
            ).run("balancer.yml")
        )
    """

    def __init__(
        self,
        base_url: str,
        endpoints: dict[str, EndpointProbeConfig],
        storage: str | None = None,
        strategy: str = "round-robin",
        health_endpoint: str = "/health",
        health_check_interval: int = 10,
        queue_timeout: float = 30.0,
        probe_on_startup: bool = True,
        force_reprobe: bool = False,
        error_threshold: float = 0.05,
        latency_threshold_ms: float = 2000.0,
        ui_username: str | None = None,
        ui_password: str | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._endpoints = endpoints
        self._storage = storage
        self._strategy = strategy
        self._health_endpoint = health_endpoint
        self._health_check_interval = health_check_interval
        self._queue_timeout = queue_timeout
        self._probe_on_startup = probe_on_startup
        self._force_reprobe = force_reprobe
        self._error_threshold = error_threshold
        self._latency_threshold_ms = latency_threshold_ms
        self._ui_username = ui_username
        self._ui_password = ui_password

    def build(self) -> BalancerConfig:
        return BalancerConfig(
            storage=self._storage,
            strategy=self._strategy,
            health_endpoint=self._health_endpoint,
            health_check_interval=self._health_check_interval,
            queue_timeout=self._queue_timeout,
            probe_on_startup=self._probe_on_startup,
            force_reprobe=self._force_reprobe,
            error_threshold=self._error_threshold,
            latency_threshold_ms=self._latency_threshold_ms,
            ui_username=self._ui_username,
            ui_password=self._ui_password,
            endpoints=self._endpoints,
        )

    async def run(self, output: str | Path = "balancer.yml") -> Path:
        """Probe all endpoints against the live base_url then write YAML."""
        storage = MemoryStorage()
        async with httpx.AsyncClient(timeout=120.0) as client:
            prober = Prober(
                storage=storage,
                http_client=client,
                error_threshold=self._error_threshold,
                latency_threshold_ms=self._latency_threshold_ms,
            )
            for path, probe_cfg in self._endpoints.items():
                logger.info("[bench] probing %s%s ...", self._base_url, path)
                result = await prober.probe(
                    base_url=self._base_url,
                    endpoint=path,
                    probe_config=probe_cfg,
                    force=True,
                    client=client,
                )
                logger.info(
                    "[bench] %s → max_concurrency=%d p99=%.0fms rps=%.1f",
                    path, result.max_concurrency, result.p99_latency_ms, result.rps,
                )
                # store measured capacity back into the endpoint config
                self._endpoints[path] = probe_cfg.model_copy(
                    update={"capacity": result.max_concurrency}
                )

        return self.to_yaml(output)

    def to_yaml(self, path: str | Path) -> Path:
        """Export config to YAML without probing."""
        cfg = self.build()
        data: dict = {
            "storage": cfg.storage,
            "strategy": cfg.strategy,
            "health_endpoint": cfg.health_endpoint,
            "health_check_interval": cfg.health_check_interval,
            "queue_timeout": cfg.queue_timeout,
            "probe_on_startup": cfg.probe_on_startup,
            "force_reprobe": cfg.force_reprobe,
            "error_threshold": cfg.error_threshold,
            "latency_threshold_ms": cfg.latency_threshold_ms,
        }
        if cfg.ui_username:
            data["ui_username"] = cfg.ui_username
        if cfg.ui_password:
            data["ui_password"] = cfg.ui_password
        if cfg.endpoints:
            data["endpoints"] = {
                ep: {
                    "method": pc.method,
                    **({"capacity": pc.capacity} if pc.capacity is not None else {}),
                    **({"headers": dict(pc.headers)} if pc.headers else {}),
                    **({"body": pc.body} if pc.body is not None else {}),
                }
                for ep, pc in cfg.endpoints.items()
            }

        out = Path(path)
        out.write_text(yaml.dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False))
        logger.info("[bench] config written to %s", out.resolve())
        return out
