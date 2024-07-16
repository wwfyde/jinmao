import asyncio
from pathlib import Path

import redis.asyncio as redis

from crawler.config import settings


async def main():
    r = redis.from_url(settings.redis_dsn, decode_responses=True, protocol=3)
    async with r:
        base_dir = Path.home().joinpath("wow-trend")
        for dir in base_dir.iterdir():
            if dir.is_dir():
                meeting_id = dir.name.split("_")[0]
                print(meeting_id)
                result = await r.delete(f"wowtrend:2025chunxia:{meeting_id}")
                print(result)


if __name__ == '__main__':
    asyncio.run(main())
