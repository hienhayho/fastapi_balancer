# Parameters Reference

---

## BalancerConfig

Passed to `Balancer(config=BalancerConfig(...))` or loaded from a YAML file via `Balancer(config="balancer.yml")`.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `storage` | `str \| None` | `None` | Redis URL (e.g. `"redis://localhost:6379"`) or `None` for in-memory storage. In-memory storage is process-local and not suitable for multi-worker deployments. |
| `strategy` | `str` | `"round-robin"` | Backend routing strategy. Accepted values: `round-robin`, `least-connections`, `weighted`. With a single backend (the default), this has no effect. |
| `health_endpoint` | `str` | `"/health"` | Path on the app to ping for liveness checks. The health checker polls this endpoint on every backend at `health_check_interval` seconds. If it returns a non-2xx status, the backend is marked unhealthy and the middleware returns `503`. |
| `health_check_interval` | `int` | `10` | Seconds between health check polls. |
| `queue_timeout` | `float` | `30.0` | Maximum seconds a request will wait in the admission queue before the middleware returns `504 Gateway Timeout`. Set to a value that matches your client's patience. |
| `probe_on_startup` | `bool` | `True` | Run throughput probing on startup. If `False`, no capacity limits are enforced and all requests pass through (unless `capacity` is set per endpoint). |
| `force_reprobe` | `bool` | `False` | Ignore any cached capacity in Redis and re-probe every endpoint from scratch. Useful after a model change or hardware upgrade. Only applies to endpoints without a manual `capacity` set. |
| `error_threshold` | `float` | `0.05` | Fraction of requests (0–1) that may fail before the prober stops stepping up. At `0.05`, probing stops as soon as more than 5% of requests return a non-2xx response. |
| `latency_threshold_ms` | `float` | `2000.0` | p99 latency in milliseconds above which the prober stops stepping up. Set this to the maximum response time your clients can tolerate. |
| `ui_username` | `str \| None` | `None` | Username for HTTP Basic Auth on the dashboard UI at `/balancer/ui`. If either `ui_username` or `ui_password` is `None`, the UI is open with no authentication. |
| `ui_password` | `str \| None` | `None` | Password for HTTP Basic Auth on the dashboard UI. |
| `endpoints` | `dict[str, EndpointProbeConfig]` | `{}` | Per-endpoint probe configuration. Keys are URL paths (e.g. `"/predict"`). Values are `EndpointProbeConfig` objects. Endpoints listed in `balancer.wrap(app, endpoints=[...])` but absent from this map use default probe settings (GET, no body, no headers). |

---

## EndpointProbeConfig

Configures how a single endpoint is probed and optionally sets a fixed capacity.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `method` | `str` | `"GET"` | HTTP method used when probing this endpoint. Must match the method your handler accepts (typically `"POST"` for inference endpoints). |
| `headers` | `dict[str, str]` | `{}` | HTTP headers sent with every probe request. Use this to pass `Authorization`, `Content-Type`, or any other required headers. |
| `body` | `dict \| None` | `None` | JSON request body sent with every probe request. Must be a valid payload that your endpoint accepts without error. |
| `capacity` | `int \| None` | `None` | If set, skips probing entirely and uses this value as the concurrency cap. The prober is never invoked for this endpoint, even when `probe_on_startup=True`. Useful when you already know the safe concurrency from prior benchmarking or manual tuning. |

---

## BenchBalancer

Standalone benchmarking tool. Probes a live API over real HTTP and writes the measured capacity into a YAML config file for later use with `Balancer`.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `base_url` | `str` | — | Base URL of the running API (e.g. `"http://localhost:8005"`). Trailing slashes are stripped automatically. |
| `endpoints` | `dict[str, EndpointProbeConfig]` | — | Map of endpoint paths to probe configs. Same format as `BalancerConfig.endpoints`. |
| `storage` | `str \| None` | `None` | Redis URL to write the probe result into. If `None`, an in-memory store is used (result is only written to the YAML file). |
| `strategy` | `str` | `"round-robin"` | Routing strategy to embed in the output YAML. |
| `health_endpoint` | `str` | `"/health"` | Health endpoint path to embed in the output YAML. |
| `health_check_interval` | `int` | `10` | Health check interval to embed in the output YAML. |
| `queue_timeout` | `float` | `30.0` | Queue timeout to embed in the output YAML. |
| `probe_on_startup` | `bool` | `True` | Value of `probe_on_startup` written to the output YAML. Set to `False` after benchmarking so the app uses the measured capacity directly without re-probing. |
| `force_reprobe` | `bool` | `False` | Value of `force_reprobe` written to the output YAML. |
| `error_threshold` | `float` | `0.05` | Error threshold used during probing and embedded in the output YAML. |
| `latency_threshold_ms` | `float` | `2000.0` | Latency threshold used during probing and embedded in the output YAML. |
| `ui_username` | `str \| None` | `None` | UI Basic Auth username to embed in the output YAML. |
| `ui_password` | `str \| None` | `None` | UI Basic Auth password to embed in the output YAML. |

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
| `504 Gateway Timeout` | Request waited longer than `queue_timeout` seconds in the admission queue. |
| `200 OK` | Normal pass-through to the actual handler. |

---

## Built-in Routes

Registered automatically by `balancer.wrap()`:

| Route | Method | Auth | Description |
|---|---|---|---|
| `/balancer/stats` | GET | None | JSON snapshot of capacity, active requests, and available slots per endpoint. |
| `/balancer/ui` | GET | Basic Auth (if configured) | Dashboard web UI. Only served when `dashboard/dist/` exists in the project root. |
| `/balancer/ui/assets/*` | GET | None | Static assets for the dashboard. |
