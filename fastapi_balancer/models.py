from datetime import datetime
from pydantic import BaseModel


class EndpointProbeConfig(BaseModel):
    method: str = "GET"
    headers: dict[str, str] = {}
    body: dict | None = None
    capacity: int | None = None  # if set, skip probing and use this value directly


class ProbeResult(BaseModel):
    backend_url: str
    endpoint: str
    max_concurrency: int
    p99_latency_ms: float
    rps: float
    probed_at: datetime


class BackendState(BaseModel):
    url: str
    healthy: bool = True
    active_requests: int = 0
    capacity: int | None = None
