import redis.asyncio as redis

from crawler.config import settings

subcategory = "dresses"
# source_key = f"target_index:target:women:{subcategory}:batch4"
target_keys = "target_index:target:men:*"


async def main():
    r = redis.from_url(settings.redis_dsn, decode_responses=True, protocol=3)
    async with r:
        keys = await r.keys(target_keys)
        print(keys)
        for key in keys:
            # 查看当前target_key 商品数量
            target_count = await r.scard(key)
            print(f"Target key {key} has {target_count} URLs.")


if __name__ == '__main__':
    import asyncio

    asyncio.run(main())
