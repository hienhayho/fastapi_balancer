from .storage.base import AbstractStorage


async def get_stats(storage: AbstractStorage, endpoints: list[str]) -> dict:
    result: dict[str, dict] = {}
    for endpoint in endpoints:
        capacity = await storage.get_capacity(endpoint)
        active = await storage.get_active(endpoint)
        result[endpoint] = {
            "capacity": capacity,
            "active_requests": active,
            "available_slots": max(0, capacity - active),
        }
    return {"endpoints": result}
