import asyncio
import redis.asyncio as redis

from crawler.config import settings


async def main():
    r = redis.from_url(settings.redis_dsn, decode_responses=True, protocol=3)
    sub_categories = []
    async with r:
        keys = r.scan_iter(match="next:men:*")
        async for key in keys:
            print(key)
            sub_categories.append(key.split(":")[-1])
        print(sub_categories)
        # value = await r.get(key)
        # print(value)


redis_client = redis.from_url(settings.redis_dsn, decode_responses=True, protocol=3)

if __name__ == '__main__':
    asyncio.run(main())
