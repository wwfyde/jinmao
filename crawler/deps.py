import asyncio

import redis.asyncio as redis

from crawler.config import settings


def _get_redis() -> redis.Redis:
    pool = redis.ConnectionPool(
        host=settings.redis.host,
        port=settings.redis.port,
        password=settings.redis.password,
        db=settings.redis.db,
        decode_responses=True,
        protocol=3,
    )
    r = redis.Redis(connection_pool=pool, decode_responses=True, protocol=3)
    return r


redis_client = _get_redis()


async def main():
    # await redis_client.set("foo", "bar")
    print(redis_client.get("a"))


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(main())
    finally:
        loop.close()
