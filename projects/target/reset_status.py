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
#     pattern = f"image_status:target:women:default*:{product}*"
#     delete_keys_by_pattern(pattern)

if __name__ == "__main__":
    # image_pattern = "image_status:target:women*"
    # main_pattern = "status:target*"
    # image_download_pattern = "image_download_status:target:women*"
    # # image_pattern = "image_status:target:men:default*"
    # review_pattern = "review_status:target:women*"
    # # delete_keys_by_pattern(image_pattern)
    # # delete_keys_by_pattern(image_download_pattern)
    # delete_keys_by_pattern(main_pattern)
    # # delete_keys_by_pattern(review_pattern)

    brand_pattern = "image_do:target:women:dresses:*"
    delete_keys_by_pattern(brand_pattern)

    # products = []
    # for product in products:
    #     image_pattern = f"image_status:target:men:default:{product}*"
    #     main_pattern = f"status:target:men:default:{product}*"
    #     image_download_pattern = f"image_download_status:target:men:default:{product}*"
    #     # image_pattern = "image_status:target:men:default*"
    #     delete_keys_by_pattern(image_pattern)
    #     delete_keys_by_pattern(image_download_pattern)
    #     delete_keys_by_pattern(main_pattern)
