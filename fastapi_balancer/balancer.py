import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, Request
import base64
import secrets

from starlette.responses import JSONResponse, FileResponse, Response
from starlette.staticfiles import StaticFiles

from fastapi_balancer.config import BalancerConfig
from fastapi_balancer.health import HealthChecker
from fastapi_balancer.limiter import Limiter
from fastapi_balancer.middleware import BalancerMiddleware
from fastapi_balancer.prober import Prober
from fastapi_balancer.router import get_router
from fastapi_balancer.stats import get_stats
from fastapi_balancer.storage import get_storage

logger = logging.getLogger(__name__)


class Balancer:
    def __init__(
        self,
        config: str | Path | BalancerConfig | None = None,
        **kwargs,
    ) -> None:
        if isinstance(config, BalancerConfig):
            self._config = config
        elif config is not None:
            self._config = BalancerConfig.from_yaml(config)
        else:
            self._config = BalancerConfig(**kwargs)

    def wrap(self, app: FastAPI) -> None:
        cfg = self._config
        endpoints = list(cfg.endpoints.keys())
        original_lifespan = app.router.lifespan_context

        logger.info(
            "fastapi-balancer initializing — endpoints=%s routing_strategy=%s storage=%s",
            endpoints,
            cfg.routing_strategy.value,
            cfg.storage.type.value,
        )

        storage = get_storage(cfg.storage)
        http_client = httpx.AsyncClient()
        prober = Prober(
            storage, http_client, cfg.error_threshold, cfg.latency_threshold_ms
        )
        health_checker = HealthChecker(storage, app)
        router = get_router(cfg.routing_strategy, storage)
        limiter = Limiter(storage)

        logger.info(
            "middleware registered for %d endpoint(s): %s", len(endpoints), endpoints
        )

        probe_base_url = "http://localhost"

        @asynccontextmanager
        async def lifespan(a: FastAPI):
            # run original lifespan first if any
            if original_lifespan:
                async with original_lifespan(a):
                    await self._startup(app, endpoints, cfg, storage, prober, health_checker, probe_base_url)
                    yield
                    await self._shutdown(health_checker, http_client, storage)
            else:
                await self._startup(app, endpoints, cfg, storage, prober, health_checker, probe_base_url)
                yield
                await self._shutdown(health_checker, http_client, storage)

        app.router.lifespan_context = lifespan

        # inject middleware
        backends = [probe_base_url]
        endpoint_queue_timeouts = {
            path: pc.queue_timeout
            for path, pc in cfg.endpoints.items()
            if pc.queue_timeout is not None
        }
        app.add_middleware(
            BalancerMiddleware,
            watched_endpoints=endpoints,
            backends=backends,
            router=router,
            limiter=limiter,
            storage=storage,
            queue_timeout=cfg.queue_timeout,
            endpoint_queue_timeouts=endpoint_queue_timeouts,
        )

        # register /balancer/stats route
        @app.get("/balancer/stats", include_in_schema=False)
        async def balancer_stats():
            return JSONResponse(await get_stats(storage, endpoints))

        # serve dashboard UI from dashboard/dist if it exists
        # installed package: fastapi_balancer/dashboard_dist/
        # local dev: dashboard/dist/ at repo root
        ui_dist = Path(__file__).parent / "dashboard_dist"
        if not ui_dist.is_dir():
            ui_dist = Path(__file__).parent.parent / "dashboard" / "dist"
        if ui_dist.is_dir() and cfg.ui.enable:
            ui_path = cfg.ui.path.rstrip("/")
            app.mount(
                f"{ui_path}/assets",
                StaticFiles(directory=str(ui_dist / "assets")),
                name="balancer_assets",
            )

            ui_username = cfg.ui.username
            ui_password = cfg.ui.password

            def _check_basic_auth(authorization: str | None) -> bool:
                if not authorization or not authorization.startswith("Basic "):
                    return False
                try:
                    decoded = base64.b64decode(authorization[6:]).decode()
                    user, _, pwd = decoded.partition(":")
                except Exception:
                    return False
                return secrets.compare_digest(
                    user, ui_username or ""
                ) and secrets.compare_digest(pwd, ui_password or "")

            @app.get(ui_path, include_in_schema=False)
            @app.get(f"{ui_path}/{{_:path}}", include_in_schema=False)
            async def balancer_ui(request: Request, _: str = ""):
                if ui_username and ui_password:
                    if not _check_basic_auth(request.headers.get("authorization")):
                        return Response(
                            content="Unauthorized",
                            status_code=401,
                            headers={"WWW-Authenticate": 'Basic realm="Balancer UI"'},
                        )
                return FileResponse(str(ui_dist / "index.html"))

            logger.info("dashboard UI mounted at %s", ui_path)

    async def _startup(self, app, endpoints, cfg, storage, prober, health_checker, base_url):
        logger.info(
            "balancer startup — probe_on_startup=%s queue_timeout=%.1fs health_check_interval=%ds",
            cfg.probe_on_startup,
            cfg.queue_timeout,
            cfg.health_check_interval,
        )

        # always apply manual capacity overrides regardless of probe_on_startup
        for endpoint in endpoints:
            probe_cfg = cfg.endpoints.get(endpoint)
            if probe_cfg is not None and probe_cfg.capacity is not None:
                await storage.set_capacity(endpoint, probe_cfg.capacity)
                logger.info(
                    "[capacity] %s — manual capacity=%d", endpoint, probe_cfg.capacity
                )

        if cfg.probe_on_startup:
            if cfg.force_reprobe:
                logger.info(
                    "force_reprobe=True — clearing cached capacity from storage"
                )
                for endpoint in endpoints:
                    probe_cfg = cfg.endpoints.get(endpoint)
                    if probe_cfg is None or probe_cfg.capacity is None:
                        await storage.set_capacity(endpoint, 0)
                        await storage.release_probe_lock(endpoint)

            logger.info(
                "starting throughput probing for %d endpoint(s) ...", len(endpoints)
            )
            transport = httpx.ASGITransport(app=app)
            probe_client = httpx.AsyncClient(transport=transport, base_url=base_url)
            for endpoint in endpoints:
                probe_cfg = cfg.endpoints.get(endpoint)
                if probe_cfg is None:
                    from fastapi_balancer.models import EndpointProbeConfig

                    probe_cfg = EndpointProbeConfig()

                if probe_cfg.capacity is not None:
                    logger.info(
                        "[probe] %s — skipping probe, manual capacity=%d already set",
                        endpoint,
                        probe_cfg.capacity,
                    )
                    continue

                # wait for endpoint to be ready before probing
                await self._wait_for_endpoint(probe_client, endpoint, probe_cfg)

                logger.info("[probe] %s — method=%s", endpoint, probe_cfg.method)
                result = await prober.probe(
                    base_url,
                    endpoint,
                    probe_cfg,
                    force=cfg.force_reprobe,
                    client=probe_client,
                )
                logger.info(
                    "[probe] %s — max_concurrency=%d p99=%.1fms rps=%.1f",
                    endpoint,
                    result.max_concurrency,
                    result.p99_latency_ms,
                    result.rps,
                )
            await probe_client.aclose()
            logger.info("probing complete for all endpoints")
        else:
            logger.warning(
                "probe_on_startup=False — capacity limits not set, all requests will pass through"
            )

        logger.info(
            "starting health checker — endpoint=%s interval=%ds",
            cfg.health_endpoint,
            cfg.health_check_interval,
        )
        health_checker.start(
            backends=[base_url],
            health_endpoint=cfg.health_endpoint,
            interval=cfg.health_check_interval,
        )
        logger.info("balancer ready")

    async def _wait_for_endpoint(
        self,
        client: httpx.AsyncClient,
        endpoint: str,
        probe_cfg,
        max_wait: int = 60,
        interval: float = 2.0,
    ) -> None:
        from .models import EndpointProbeConfig

        logger.info("waiting for %s to be ready ...", endpoint)
        for attempt in range(int(max_wait / interval)):
            try:
                resp = await client.request(
                    method=probe_cfg.method,
                    url=endpoint,
                    headers=probe_cfg.headers,
                    json=probe_cfg.body,
                    timeout=10.0,
                )
                if resp.status_code < 500:
                    logger.info("%s is ready (status=%d)", endpoint, resp.status_code)
                    return
                logger.info(
                    "waiting for %s — got status=%d, retrying in %.0fs ...",
                    endpoint,
                    resp.status_code,
                    interval,
                )
            except Exception as e:
                logger.info(
                    "waiting for %s — %s, retrying in %.0fs ...", endpoint, e, interval
                )
            await asyncio.sleep(interval)
        logger.warning(
            "gave up waiting for %s after %ds — probing anyway", endpoint, max_wait
        )

    async def _shutdown(self, health_checker, http_client, storage):
        logger.info("balancer shutting down ...")
        await health_checker.stop()
        logger.info("health checker stopped")
        await http_client.aclose()
        await storage.close()
        logger.info("balancer shutdown complete")
