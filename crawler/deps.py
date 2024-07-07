import asyncio
import logging
from logging.handlers import RotatingFileHandler
from typing import AsyncGenerator

import redis.asyncio as redis

from crawler.config import settings


async def create_pool() -> redis.ConnectionPool:
    pool = redis.ConnectionPool(
        host=settings.redis.host,
        port=settings.redis.port,
        password=settings.redis.password,
        db=settings.redis.db,
        decode_responses=True,
        protocol=3,
    )
    # r = redis.Redis(connection_pool=pool, decode_responses=True, protocol=3)
    return pool


async def get_redis_cache() -> AsyncGenerator[redis.Redis, None]:
    pool = redis.ConnectionPool.from_url(settings.redis_dsn, decode_responses=True, protocol=3)
    r = redis.Redis(connection_pool=pool, decode_responses=True, protocol=3)
    async with r:
        print(await r.get("a"))
        yield r


class RedisClient:
    _pool = None

    @classmethod
    async def initialize(cls):
        if cls._pool is None:
            cls._pool = await create_pool()

    @classmethod
    async def get_client(cls) -> redis.Redis:
        await cls.initialize()
        return redis.Redis(connection_pool=cls._pool, decode_responses=True)


def get_logger(name: str = __name__):
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)  # 设置日志级别

    log_file = settings.log_file_path.joinpath("target.log")
    handler = RotatingFileHandler(log_file, maxBytes=1000000, backupCount=3)
    handler.setLevel(logging.WARNING)  # 设置处理器的日志级别
    formatter = logging.Formatter("%(asctime)s | %(name)s | %(levelname)s | %(message)s [in %(pathname)s:%(lineno)d]")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    # 创建标准输出处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)  # 设置处理器的日志级别
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    return logger


async def main():
    # await redis_client.set("foo", "bar")
    # redis_client = await RedisClient.get_client()
    # print(await redis_client.get("a"))
    r = redis.from_url(settings.redis_dsn, decode_responses=True, protocol=3)
    async with r:
        print(await r.get("a"))
    # return
    async with await get_redis_cache().__anext__() as r:
        print(await r.get("a"))

    # r = redis.from_url(settings.redis_dsn, decode_responses=True, protocol=3)
    # async with r:
    #     print(await r.get("a"))


if __name__ == "__main__":
    # loop = asyncio.get_event_loop()
    # try:
    #     loop.run_until_complete(main())
    # finally:
    #     loop.close()
    asyncio.run(main())
