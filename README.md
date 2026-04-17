# fastapi-balancer

A Python library for auto-probing the throughput ceiling of FastAPI endpoints and enforcing admission control to prevent overload. It measures how many concurrent requests your endpoint can safely handle, then enforces that limit at runtime by queuing excess requests rather than dropping them.

---

## Table of Contents

- [Overview](#overview)
- [How It Works](#how-it-works)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Usage](#usage)
  - [Inline Config](#inline-config)
  - [YAML Config](#yaml-config)
  - [Manual Capacity](#manual-capacity)
  - [Per-Endpoint Queue Timeout](#per-endpoint-queue-timeout)
  - [Multi-Worker Deployment](#multi-worker-deployment)
  - [Dashboard UI](#dashboard-ui)
- [BenchBalancer](#benchbalancer)
- [Built-in Endpoints](#built-in-endpoints)
- [Parameters](#parameters)
- [License](#license)

---

## Overview

When running a FastAPI app with compute-heavy endpoints (LLM inference, scoring models, image processing), sending too many concurrent requests causes latency to spike, memory to exhaust, and the service to become unresponsive. Traditional solutions require manual tuning or external infrastructure.

`fastapi-balancer` solves this by:

1. **Auto-probing** — at startup, it sends increasing levels of concurrent requests to your endpoint and finds the maximum concurrency at which it remains stable (within your error rate and latency thresholds).
2. **Admission control** — a middleware intercepts every incoming request to watched endpoints, admits up to the measured capacity, and queues the rest. Requests only fail with a `504` if they wait longer than `queue_timeout` seconds — no requests are silently dropped.
3. **Cross-worker coordination** — when running multiple uvicorn workers, a Redis-backed counter ensures the global in-flight count stays within capacity across all processes.
4. **Dashboard** — a built-in web UI (configurable path, default `/balancer/ui`) shows live capacity, active requests, queue depth, and a 60-second time-series chart per endpoint.

---

## How It Works

### Throughput Probing

The prober sends batches of concurrent requests to each watched endpoint using step-up concurrency levels: 1, 2, 4, 8, 16, 32, 64, 128, ... At each level it measures:

- Error rate (non-2xx responses)
- p99 latency
- RPS

Probing stops when either `error_threshold` or `latency_threshold_ms` is exceeded. A binary search then refines the result between the last passing level and the first failing level. The result (`max_concurrency`) is saved to storage and used as the admission cap.

### Admission Control

Every request to a watched endpoint goes through the middleware:

1. Check backend health — return `503` if unhealthy.
2. Attempt to acquire a slot (increment active counter).
3. If slots are full — place request in a FIFO queue, wait up to `queue_timeout` seconds.
4. If queue wait expires — return `504 Gateway Timeout`.
5. Otherwise — pass request to the actual handler, release slot on completion.

### Request Flow

```
Incoming request
    |
    v
BalancerMiddleware
    |-- path not watched? --> pass through unchanged
    |-- backend unhealthy? --> 503
    |-- slot available? --> admit, call handler, release slot
    |-- slots full --> FIFO queue, wait for release
    |-- queue timeout --> 504
```

---

## Installation

### From PyPI

```bash
uv add fastapi-balancer
```

The published wheel includes the pre-built dashboard. No Node.js or pnpm required.

### From source

Clone the repository and build the wheel. The build step automatically runs `pnpm install && pnpm build` inside `dashboard/` and bundles the output into the package — pnpm must be available on your `PATH`.

```bash
git clone https://github.com/hienhayho/fastapi_balancer.git
cd fastapi_balancer
uv build
uv add dist/fastapi_balancer-*.whl
```

To skip the dashboard (no Node.js needed), remove or rename the `dashboard/` directory before building — the build hook silently skips the frontend step when the directory is absent.

### Local development (editable install)

```bash
git clone https://github.com/hienhayho/fastapi_balancer.git
cd fastapi_balancer
uv sync --extra dev
```

In editable mode the app serves the dashboard directly from `dashboard/dist/` — run the frontend build separately when you want the UI:

```bash
cd dashboard
pnpm install
pnpm build
```

Redis is a required dependency. Ensure a Redis server is accessible when using multi-worker deployments.

---

## Quick Start

```python
from fastapi import FastAPI
from fastapi_balancer import Balancer, BalancerConfig, StorageConfig, StorageType
from fastapi_balancer.models import EndpointProbeConfig

app = FastAPI()

# ... include your routers ...

balancer = Balancer(
    config=BalancerConfig(
        storage=StorageConfig(type=StorageType.REDIS, url="redis://localhost:6379"),
        probe_on_startup=True,
        queue_timeout=30.0,
        endpoints={
            "/predict": EndpointProbeConfig(
                method="POST",
                headers={"Authorization": "Bearer your-token"},
                body={"input": "sample"},
            )
        },
    )
)

balancer.wrap(app)
```

On startup the balancer probes `/predict`, stores its capacity, and begins enforcing the limit on every incoming request.

---

## Usage

### Inline Config

```python
from fastapi_balancer import Balancer, BalancerConfig, RoutingStrategy, StorageConfig, StorageType, UIConfig
from fastapi_balancer.models import EndpointProbeConfig

balancer = Balancer(
    config=BalancerConfig(
        storage=StorageConfig(type=StorageType.REDIS, url="redis://localhost:6379"),
        routing_strategy=RoutingStrategy.ROUND_ROBIN,
        probe_on_startup=True,
        queue_timeout=60.0,
        latency_threshold_ms=10000,
        ui=UIConfig(username="admin", password="secret"),
        endpoints={
            "/ai_score": EndpointProbeConfig(
                method="POST",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": "Bearer your-token",
                },
                body={"inputs": [...], "language": "en"},
            )
        },
    )
)

balancer.wrap(app)
```

### YAML Config

```python
balancer = Balancer(config="balancer.yml")
balancer.wrap(app)
```

Example `balancer.yml`:

```yaml
storage:
  type: redis
  url: redis://localhost:6379

routing_strategy: round-robin
health_endpoint: /health
health_check_interval: 10
queue_timeout: 30
probe_on_startup: true
force_reprobe: false
error_threshold: 0.05
latency_threshold_ms: 2000

ui:
  enable: true
  path: /balancer/ui
  username: admin
  password: secret

endpoints:
  /predict:
    method: POST
    headers:
      Content-Type: application/json
      Authorization: Bearer your-token
    body:
      input: "sample input"
  /embed:
    method: POST
    headers:
      Content-Type: application/json
    body:
      texts: ["hello"]
```

See `balancer.yml.example` for the full annotated template.

### Manual Capacity

If you already know the safe concurrency for an endpoint, set `capacity` directly to skip probing entirely. This works even when `probe_on_startup=True`.

```python
endpoints={
    "/predict": EndpointProbeConfig(
        method="POST",
        capacity=10,  # use this, skip probing
    )
}
```

Or in YAML:

```yaml
endpoints:
  /predict:
    method: POST
    capacity: 10
```

### Per-Endpoint Queue Timeout

Override the global `queue_timeout` for a specific endpoint using `EndpointProbeConfig.queue_timeout`. Useful when different endpoints have different client patience levels.

```python
endpoints={
    "/predict": EndpointProbeConfig(
        method="POST",
        queue_timeout=120.0,  # long-running inference — wait up to 2 minutes
    ),
    "/health": EndpointProbeConfig(
        method="GET",
        queue_timeout=5.0,   # health checks should fail fast
    ),
}
```

Or in YAML:

```yaml
queue_timeout: 30  # global default

endpoints:
  /predict:
    method: POST
    queue_timeout: 120
  /health:
    method: GET
    queue_timeout: 5
```

### Multi-Worker Deployment

When running uvicorn with multiple workers, each worker is an independent process. In-memory storage cannot be shared across processes. Use Redis so all workers share a single global counter:

```bash
uvicorn main:app --workers 4
```

```python
BalancerConfig(
    storage=StorageConfig(type=StorageType.REDIS, url="redis://localhost:6379")
)
```

Without Redis, each worker probes independently and tracks its own active count — leading to the total in-flight count being `workers x capacity` instead of `capacity`.

With Redis:

- The first worker to start probes the endpoint and writes the result.
- Subsequent workers see the result already in Redis and skip probing.
- All workers share a single atomic counter for active requests.

If you need to force all workers to re-probe (e.g. after a model change), set `force_reprobe=True` for one restart, then remove it.

### Dashboard UI

The dashboard is mounted at `ui.path` (default `/balancer/ui`) and auto-detects the API base URL from `window.location.origin`.

To protect it with a password:

```python
UIConfig(username="admin", password="secret")
```

To change the mount path:

```python
UIConfig(path="/dashboard", username="admin", password="secret")
```

To disable the dashboard entirely:

```python
UIConfig(enable=False)
```

The browser will show its native Basic Auth popup when credentials are configured. Without `username`/`password`, the UI is open.

The dashboard polls `/balancer/stats` every 2 seconds and shows:

- Per-endpoint capacity, active requests, available slots, utilization percentage
- Health status (green / yellow at 80% / red at 100%)
- Queue depth badge when active requests exceed capacity
- 60-second time-series chart of active requests per endpoint

---

## BenchBalancer

`BenchBalancer` is a standalone tool for probing a live API from outside — without wrapping a FastAPI app. Run it as a script before deploying, then use the generated YAML in production with `probe_on_startup=False`.

```python
import asyncio
from fastapi_balancer import BenchBalancer, StorageConfig, StorageType, UIConfig
from fastapi_balancer.models import EndpointProbeConfig

asyncio.run(
    BenchBalancer(
        base_url="http://localhost:8005",
        endpoints={
            "/ai_score": EndpointProbeConfig(
                method="POST",
                headers={"Authorization": "Bearer your-token"},
                body={"inputs": [...], "language": "en"},
            )
        },
        storage=StorageConfig(type=StorageType.REDIS, url="redis://localhost:6379"),
        latency_threshold_ms=80000,
        error_threshold=0.05,
        queue_timeout=90.0,
        ui=UIConfig(username="admin", password="secret"),
    ).run("balancer.yml")
)
```

`run()` probes each endpoint against the live server, measures `max_concurrency`, writes the result into the YAML as `capacity`, then saves the file. The output YAML is ready to be passed directly to `Balancer(config="balancer.yml")`.

To export config without probing (e.g. just serialize existing settings):

```python
bench = BenchBalancer(base_url="http://localhost:8005", endpoints={...})
bench.to_yaml("balancer.yml")
```

---

## Built-in Endpoints

These endpoints are automatically registered on the wrapped app:

| Endpoint | Method | Description |
|---|---|---|
| `/balancer/stats` | GET | JSON with capacity, active requests, available slots per endpoint |
| `<ui.path>` | GET | Dashboard web UI (default `/balancer/ui`) |

### `/balancer/stats` response shape

```json
{
  "endpoints": {
    "/predict": {
      "capacity": 50,
      "active_requests": 12,
      "available_slots": 38
    }
  }
}
```

---

## Parameters

For a full reference of all configuration parameters, see [PARAMS.md](PARAMS.md).

---

## License

MIT
