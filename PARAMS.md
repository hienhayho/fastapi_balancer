# Parameters Reference

---

## BalancerConfig

Passed to `Balancer(config=BalancerConfig(...))` or loaded from a YAML file via `Balancer(config="balancer.yml")`.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `storage` | `StorageConfig` | `StorageConfig()` | Storage backend configuration. See [StorageConfig](#storageconfig). Defaults to in-memory storage. |
| `routing_strategy` | `RoutingStrategy` | `RoutingStrategy.ROUND_ROBIN` | Backend routing strategy. See [RoutingStrategy](#routingstrategy). With a single backend (the default), this has no effect. |
| `health_endpoint` | `str` | `"/health"` | Path on the app to ping for liveness checks. The health checker polls this endpoint at `health_check_interval` seconds. If it returns a non-2xx status, the backend is marked unhealthy and the middleware returns `503`. |
| `health_check_interval` | `int` | `10` | Seconds between health check polls. |
| `queue_timeout` | `float` | `30.0` | Global default — maximum seconds a request will wait in the admission queue before the middleware returns `504 Gateway Timeout`. Can be overridden per endpoint via `EndpointProbeConfig.queue_timeout`. |
| `probe_on_startup` | `bool` | `True` | Run throughput probing on startup. If `False`, no capacity limits are enforced and all requests pass through (unless `capacity` is set per endpoint). |
| `force_reprobe` | `bool` | `False` | Ignore any cached capacity in Redis and re-probe every endpoint from scratch. Useful after a model change or hardware upgrade. Only applies to endpoints without a manual `capacity` set. |
| `error_threshold` | `float` | `0.05` | Fraction of requests (0–1) that may fail before the prober stops stepping up. At `0.05`, probing stops as soon as more than 5% of requests return a non-2xx response. |
| `latency_threshold_ms` | `float` | `2000.0` | p99 latency in milliseconds above which the prober stops stepping up. Set this to the maximum response time your clients can tolerate. |
| `ui` | `UIConfig` | `UIConfig()` | Dashboard UI configuration. See [UIConfig](#uiconfig). |
| `endpoints` | `dict[str, EndpointProbeConfig]` | `{}` | Per-endpoint probe configuration. Keys are URL paths (e.g. `"/predict"`). Values are `EndpointProbeConfig` objects. All keys in this map are automatically watched by the balancer — no need to pass them separately. |

---

## StorageConfig

Controls where active request counts and capacity values are stored.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `type` | `StorageType` | `StorageType.MEMORY` | Storage backend. `StorageType.MEMORY` is process-local and not suitable for multi-worker deployments. `StorageType.REDIS` shares state across all workers via Redis. |
| `url` | `str \| None` | `None` | Redis connection URL (e.g. `"redis://localhost:6379"`). Required when `type=StorageType.REDIS`, ignored otherwise. |

### StorageType values

| Value | Description |
|---|---|
| `StorageType.MEMORY` | In-process storage using plain dicts and asyncio locks. No external dependencies. |
| `StorageType.REDIS` | Redis-backed storage using atomic `INCR`/`DECR`. Required for multi-worker deployments. |

---

## RoutingStrategy

Enum controlling how the balancer selects a backend when multiple backends are configured. With a single backend (the default), all values behave identically.

| Value | Description |
|---|---|
| `RoutingStrategy.ROUND_ROBIN` | Cycles through backends in order. Default. |
| `RoutingStrategy.LEAST_CONNECTIONS` | Picks the backend with the fewest active requests. |
| `RoutingStrategy.WEIGHTED` | Picks the backend with the most remaining capacity (`capacity - active`). |

---

## UIConfig

Controls the built-in dashboard UI served at the configured path.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `enable` | `bool` | `True` | Set to `False` to disable the dashboard entirely. No routes are registered and no static files are served. |
| `path` | `str` | `"/balancer/ui"` | URL prefix at which the dashboard is mounted. Trailing slashes are stripped automatically. |
| `username` | `str \| None` | `None` | Username for HTTP Basic Auth. If either `username` or `password` is `None`, the UI is open with no authentication. |
| `password` | `str \| None` | `None` | Password for HTTP Basic Auth. |

---

## EndpointProbeConfig

Configures how a single endpoint is probed and optionally overrides global settings for that endpoint.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `method` | `str` | `"GET"` | HTTP method used when probing this endpoint. Must match the method your handler accepts (typically `"POST"` for inference endpoints). |
| `headers` | `dict[str, str]` | `{}` | HTTP headers sent with every probe request. Use this to pass `Authorization`, `Content-Type`, or any other required headers. |
| `body` | `dict \| None` | `None` | JSON request body sent with every probe request. Must be a valid payload that your endpoint accepts without error. |
| `capacity` | `int \| None` | `None` | If set, skips probing entirely and uses this value as the concurrency cap. The prober is never invoked for this endpoint, even when `probe_on_startup=True`. Useful when you already know the safe concurrency from prior benchmarking or manual tuning. |
| `queue_timeout` | `float \| None` | `None` | Per-endpoint queue timeout in seconds. Overrides `BalancerConfig.queue_timeout` for this endpoint only. If `None`, the global `queue_timeout` applies. |

---

## BenchBalancer

Standalone benchmarking tool. Probes a live API over real HTTP and writes the measured capacity into a YAML config file for later use with `Balancer`.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `base_url` | `str` | — | Base URL of the running API (e.g. `"http://localhost:8005"`). Trailing slashes are stripped automatically. |
| `endpoints` | `dict[str, EndpointProbeConfig]` | — | Map of endpoint paths to probe configs. Same format as `BalancerConfig.endpoints`. |
| `storage` | `StorageConfig \| None` | `None` | Storage config to embed in the output YAML. If `None`, defaults to `StorageConfig()` (memory). |
| `routing_strategy` | `RoutingStrategy` | `RoutingStrategy.ROUND_ROBIN` | Routing strategy to embed in the output YAML. |
| `health_endpoint` | `str` | `"/health"` | Health endpoint path to embed in the output YAML. |
| `health_check_interval` | `int` | `10` | Health check interval to embed in the output YAML. |
| `queue_timeout` | `float` | `30.0` | Global queue timeout to embed in the output YAML. |
| `probe_on_startup` | `bool` | `True` | Value of `probe_on_startup` written to the output YAML. Set to `False` after benchmarking so the app uses the measured capacity directly without re-probing. |
| `force_reprobe` | `bool` | `False` | Value of `force_reprobe` written to the output YAML. |
| `error_threshold` | `float` | `0.05` | Error threshold used during probing and embedded in the output YAML. |
| `latency_threshold_ms` | `float` | `2000.0` | Latency threshold used during probing and embedded in the output YAML. |
| `ui` | `UIConfig \| None` | `None` | UI config to embed in the output YAML. If `None`, defaults to `UIConfig()`. |

### Methods

| Method | Signature | Description |
|---|---|---|
| `run` | `async run(output: str \| Path = "balancer.yml") → Path` | Probes all endpoints against the live `base_url`, writes `capacity` back into each `EndpointProbeConfig`, and calls `to_yaml(output)`. Returns the path of the written file. |
| `to_yaml` | `to_yaml(path: str \| Path) → Path` | Serializes the current config (including any `capacity` values already set) to a YAML file without probing. Returns the path of the written file. |
| `build` | `build() → BalancerConfig` | Returns a `BalancerConfig` object from the current settings. |

---

## HTTP Responses

Responses added by the middleware and built-in routes:

| Status | When |
|---|---|
| `503 Service Unavailable` | Backend health check is failing. |
| `504 Gateway Timeout` | Request waited longer than the effective `queue_timeout` (endpoint-level or global) in the admission queue. |
| `200 OK` | Normal pass-through to the actual handler. |

---

## Built-in Routes

Registered automatically by `balancer.wrap(app)`:

| Route | Method | Auth | Description |
|---|---|---|---|
| `/balancer/stats` | GET | None | JSON snapshot of capacity, active requests, and available slots per endpoint. |
| `<ui.path>` | GET | Basic Auth (if configured) | Dashboard web UI. Only served when the built package includes `dashboard_dist/` or `dashboard/dist/` exists locally. Defaults to `/balancer/ui`. |
| `<ui.path>/assets/*` | GET | None | Static assets for the dashboard. |
