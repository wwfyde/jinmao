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
    # delete_keys_by_pattern(image_pattern)
    # delete_keys_by_pattern(image_download_pattern)
    # delete_keys_by_pattern(main_pattern)
    # products = [
    #     "1000080",
    #     "829184",
    #     "429892",
    #     "720206",
    #     "737296",
    #     "585699",
    #     "413831",
    #     "513718",
    #     "598134",
    #     "709142",
    #     "472757",
    #     "880824",
    #     "238137",
    #     "881249",
    #     "881251",
    #     "497104",
    #     "618700",
    #     "541753",
    #     "795282",
    #     "541759",
    #     "429217",
    #     "472760",
    #     "720137",
    #     "410337",
    #     "769041",
    #     "429574",
    #     "619568",
    #     "440460",
    #     "716455",
    #     "819576",
    #     "737295",
    #     "496157",
    #     "715036",
    #     "582435",
    # ]
    products = [  # 第一批
        793269,
        623795,
        881150,
        885499,
        881157,
        885498,
        401672,
        606506,
        735795,
        885502,
        608891,
        496861,
        608930,
        606484,
        878160,
        446216,
        431194,
        431249,
        431270,
        431230,
        431253,
        767285,
        767303,
        810231,
        370404,
        370407,
        372200,
        618357,
        790798,
        796309,
        663802,
        663803,
        709290,
        860852,
        490772,
        587820,
        767408,
        767408,
        431248,
        431256,
        431268,
        407881,
        407882,
        407884,
        670516,
        739113,
        409771,
        409769,
        407815,
        407828,
        407852,
        432724,
        432755,
        432732,
        432726,
        432730,
        432685,
        432715,
        432481,
        432484,
        432489,
        432479,
        432497,
        407965,
        881856,
        437589,
        404639,
        437792,
        404649,
        437580,
        404622,
        446230,
        435032,
        446218,
        805041,
        858412,
    ]
    # products = [  # women
    #     793269,
    #     623795,
    #     623795,
    #     830494,
    #     881150,
    #     885499,
    #     881157,
    #     885498,
    #     885498,
    #     767285,
    #     767303,
    #     810231,
    #     681602,
    #     663802,
    #     663803,
    #     860852,
    #     709290,
    #     490772,
    #     587820,
    #     767408,
    #     739113,
    #     754457,
    # ]
    # products += [  # men
    #     401672,
    #     735795,
    #     885502,
    #     606506,
    #     736484,
    #     608891,
    #     608930,
    #     606484,
    #     878160,
    #     885500,
    #     602577,
    #     370404,
    #     370407,
    #     372200,
    #     540888,
    #     618357,
    #     790798,
    #     796309,
    #     891754,
    # ]
    # products += [  # boys
    #     838218,
    #     874579,
    #     879147,
    #     874583,
    #     870729,
    #     879170,
    #     879169,
    #     879160,
    #     879171,
    #     879129,
    #     881888,
    #     868245,
    #     881856,
    #     868288,
    #     881832,
    #     868273,
    #     805040,
    # ]
    # products += [
    #     838237,
    #     870731,
    #     879063,
    #     879078,
    #     879075,
    #     878911,
    #     879029,
    #     878916,
    #     879002,
    #     876422,
    #     868380,
    #     876415,
    #     868367,
    #     876418,
    #     886039,
    #     805041,
    # ]  # girls
    # products += [805044, 879282, 879319, 879201]  # baby_girls
    # products += [879263, 879218]  # baby_boys
    genders = ["women", "men", "girls", "boys", "baby_girls", "baby_boys"]
    for gender in genders:
        for product in products:
            image_pattern = f"image_status:gap:{gender}:default:{product}*"
            main_pattern = f"status:gap:{gender}:default:{product}*"
            image_download_pattern = f"image_download_status:gap:{gender}:default:{product}*"
            # image_pattern = "image_status:gap:men:default*"
            delete_keys_by_pattern(image_pattern)
            delete_keys_by_pattern(image_download_pattern)
            delete_keys_by_pattern(main_pattern)
