import asyncio
import redis.asyncio as redis

from crawler.config import settings


async def main():
    r = redis.from_url(settings.redis_dsn, decode_responses=True, protocol=3)

    async with r:
        keys = r.scan_iter(match="image_download_status:target:*:*:*:*")
        async for key in keys:
            print(key)
            value = await r.get(key)
            new_key_spliter = key.split(":")
            new_key = f"{new_key_spliter[0]}:{new_key_spliter[1]}:{new_key_spliter[-2]}:{new_key_spliter[-1]}"
            print(f"{new_key}:{value}")
            await r.set(new_key, value)
            await r.delete(key)


if __name__ == '__main__':
    asyncio.run(main())
