import asyncio

import redis.asyncio as redis

from crawler.config import settings


async def main():
    r = redis.from_url(settings.redis_dsn, decode_responses=True, protocol=3)
    async with r:
        pass
        keys = await r.keys("gap_search:women:*")
        pass


if __name__ == "__main__":
    asyncio.run(main())
