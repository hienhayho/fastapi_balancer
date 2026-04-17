from pathlib import Path
from pydantic import BaseModel, field_validator
import yaml

from .models import EndpointProbeConfig


class BalancerConfig(BaseModel):
    storage: str | None = None
    strategy: str = "round-robin"
    health_endpoint: str = "/health"
    health_check_interval: int = 10
    queue_timeout: float = 30.0
    probe_on_startup: bool = True
    error_threshold: float = 0.05
    latency_threshold_ms: float = 2000.0
    endpoints: dict[str, EndpointProbeConfig] = {}
    ui_username: str | None = None
    ui_password: str | None = None
    force_reprobe: bool = False

    @field_validator("strategy")
    @classmethod
    def validate_strategy(cls, v: str) -> str:
        allowed = {"round-robin", "least-connections", "weighted"}
        if v not in allowed:
            raise ValueError(f"strategy must be one of {allowed}")
        return v

    @classmethod
    def from_yaml(cls, path: str | Path) -> "BalancerConfig":
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        return cls(**data)
