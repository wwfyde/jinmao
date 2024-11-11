import asyncio

import aiofiles
import redis.asyncio as redis

from crawler.config import settings

async def main():
    pool = redis.ConnectionPool.from_url(settings.redis_dsn, decode_responses=True, )
    r = redis.Redis(connection_pool=pool, decode_responses=True)
    file_path = settings.project_dir / "products_pyjamas.txt"
    data = []
    async with aiofiles.open(file_path, mode="r") as f:
        async for line in f:
            line_parts = line.strip().split(", ", )[:2]
            data.append(", ".join(line_parts))
        print(data)
        # await r.zadd("jinmao:next:pyjams")
        # await r.lpush("jinmao:next:pyjamas", *data)
        await r.get('a')
        # await r.close()


if __name__ == '__main__':
    asyncio.run(main())
