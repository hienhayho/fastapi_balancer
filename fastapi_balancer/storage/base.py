from abc import ABC, abstractmethod


class AbstractStorage(ABC):
    @abstractmethod
    async def get_capacity(self, endpoint: str) -> int: ...

    @abstractmethod
    async def set_capacity(self, endpoint: str, value: int) -> None: ...

    @abstractmethod
    async def increment_active(self, endpoint: str) -> int: ...

    @abstractmethod
    async def decrement_active(self, endpoint: str) -> int: ...

    @abstractmethod
    async def get_active(self, endpoint: str) -> int: ...

    @abstractmethod
    async def get_health(self, backend: str) -> bool: ...

    @abstractmethod
    async def set_health(self, backend: str, value: bool) -> None: ...

    @abstractmethod
    async def close(self) -> None: ...

    @abstractmethod
    async def acquire_probe_lock(self, endpoint: str, ttl_seconds: int = 60) -> bool:
        """Try to acquire an exclusive probe lock. Returns True if acquired."""
        ...

    @abstractmethod
    async def release_probe_lock(self, endpoint: str) -> None: ...
