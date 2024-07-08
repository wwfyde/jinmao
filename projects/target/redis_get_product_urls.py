import asyncio
import redis.asyncio as redis

from crawler.config import settings


async def main():
    r = redis.from_url(settings.redis_dsn, decode_responses=True, protocol=3)

    async with r:
        source = "target"
        primary_category = "women"
        sub_category = "dresses"
        color = "black"
        product_urls = await r.smembers(f"{source}:{primary_category}:{sub_category}:{color}")
        print(product_urls)


if __name__ == '__main__':
    asyncio.run(main())
