from fastapi_balancer.storage.base import AbstractStorage
from fastapi_balancer.storage.memory import MemoryStorage
from fastapi_balancer.models import StorageConfig, StorageType


def get_storage(cfg: StorageConfig) -> AbstractStorage:
    if cfg.type == StorageType.REDIS:
        if not cfg.url:
            raise ValueError("StorageConfig.url is required when type=REDIS")
        from fastapi_balancer.storage.redis import RedisStorage
        return RedisStorage(cfg.url)
    return MemoryStorage()


__all__ = ["AbstractStorage", "MemoryStorage", "get_storage"]
