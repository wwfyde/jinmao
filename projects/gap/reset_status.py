import redis

from crawler.config import settings

# 初始化 Redis 连接
r = redis.from_url(settings.redis_dsn, decode_responses=True, protocol=3)


def delete_keys_by_pattern(pattern: str):
    """
    删除所有匹配模式的键
    :param pattern: 匹配模式
    """
    cursor = "0"
    while cursor != 0:
        cursor, keys = r.scan(cursor=cursor, match=pattern, count=1000)
        if keys:
            r.delete(*keys)
            print(f"Deleted {len(keys)} keys")


#
# for product in products:
#     pattern = f"image_status:gap:women:default*:{product}*"
#     delete_keys_by_pattern(pattern)

if __name__ == "__main__":
    image_pattern = "image_status:gap:men:default*"
    main_pattern = "status:gap:men:default*"
    image_download_pattern = "image_download_status:gap:men:default*"
    # image_pattern = "image_status:gap:men:default*"
    delete_keys_by_pattern(image_pattern)
    delete_keys_by_pattern(image_download_pattern)
    delete_keys_by_pattern(main_pattern)
