import redis.asyncio as redis

from crawler.config import settings

subcategory = "shorts"
source_key = "next:women:Blouses"
target_key = "next:women:blouses"


async def main():
    r = redis.from_url(settings.redis_dsn, decode_responses=True, protocol=3)
    async with r:
        print(f"Source key: {source_key}")
        print(f"Target key: {target_key}")

        # 获取集合下的索所有商品
        product_urls = await r.smembers(source_key)
        print(f"Found {len(product_urls)} product URLs.")

        # 将商品 URL 插入到目标集合中
        insert_count = await r.sadd(target_key, *product_urls)
        print(f"Inserted {insert_count} new URLs.")

        # 删除原有的 key
        await r.delete(source_key)

        # 查看当前target_key 商品数量
        target_count = await r.scard(target_key)
        print(f"Target key has {target_count} URLs.")


if __name__ == '__main__':
    import asyncio

    asyncio.run(main())
