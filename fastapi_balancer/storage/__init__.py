from .base import AbstractStorage
from .memory import MemoryStorage


def get_storage(url: str | None) -> AbstractStorage:
    if url is None:
        return MemoryStorage()
    from .redis import RedisStorage
    return RedisStorage(url)


__all__ = ["AbstractStorage", "MemoryStorage", "get_storage"]
