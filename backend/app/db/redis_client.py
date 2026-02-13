"""
Redis client initialization.
Provides both sync and async Redis connections.
"""

import redis
import redis.asyncio as aioredis
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from shared_config import settings

# Sync Redis client (for worker)
sync_redis: redis.Redis = None

# Async Redis client (for FastAPI)
async_redis: aioredis.Redis = None


def get_sync_redis() -> redis.Redis:
    """Get or create sync Redis client."""
    global sync_redis
    if sync_redis is None:
        sync_redis = redis.from_url(settings.REDIS_URL, decode_responses=True)
    return sync_redis


async def get_async_redis() -> aioredis.Redis:
    """Get or create async Redis client."""
    global async_redis
    if async_redis is None:
        async_redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    return async_redis
