from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class StorageType(str, Enum):
    MEMORY = "memory"
    REDIS = "redis"


class RoutingStrategy(str, Enum):
    ROUND_ROBIN = "round-robin"
    LEAST_CONNECTIONS = "least-connections"
    WEIGHTED = "weighted"


class StorageConfig(BaseModel):
    type: StorageType = StorageType.MEMORY
    url: str | None = None  # required when type=REDIS


class UIConfig(BaseModel):
    enable: bool = True
    path: str = "/balancer/ui"
    username: str | None = None
    password: str | None = None


class EndpointProbeConfig(BaseModel):
    method: str = "GET"
    headers: dict[str, str] = {}
    body: dict | None = None
    capacity: int | None = None  # if set, skip probing and use this value directly
    queue_timeout: float | None = None  # overrides BalancerConfig.queue_timeout if set


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
