import redis.asyncio as redis
from crawler.config import settings

key_pattern = 'category_task_status:next:girls:*'


async def main():
    r = redis.from_url(settings.redis_dsn, decode_responses=True, protocol=3)
    async with r:
        keys = await r.keys(key_pattern)
        print(keys)
        for key in keys:
            # 删除原有的 key
            await r.delete(key)
            print(f"Deleted key {key}")
        #     # 查看当前target_key 商品数量
        #     target_count = await r.scard(key)
        #     print(f"Target key {key} has {target_count} URLs.")


if __name__ == '__main__':
    import asyncio

    asyncio.run(main())
