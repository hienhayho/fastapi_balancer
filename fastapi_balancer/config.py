from pathlib import Path
from pydantic import BaseModel
import yaml

from fastapi_balancer.models import EndpointProbeConfig, RoutingStrategy, StorageConfig, UIConfig


class BalancerConfig(BaseModel):
    storage: StorageConfig = StorageConfig()
    routing_strategy: RoutingStrategy = RoutingStrategy.ROUND_ROBIN
    health_endpoint: str = "/health"
    health_check_interval: int = 10
    queue_timeout: float = 30.0
    probe_on_startup: bool = True
    error_threshold: float = 0.05
    latency_threshold_ms: float = 2000.0
    endpoints: dict[str, EndpointProbeConfig] = {}
    ui: UIConfig = UIConfig()
    force_reprobe: bool = False

    @classmethod
    def from_yaml(cls, path: str | Path) -> "BalancerConfig":
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        return cls(**data)
