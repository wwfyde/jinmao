import requests

file_path = r"C:\爬虫图片\男明星\秦岚超话"  # 文件路径


def get_nested_value(data, keys, default=None):
    """
    从嵌套的 JSON 数据中获取特定的值。

    参数:
    - data: JSON 数据 (Python 字典格式)
    - keys: 键列表，用于指示要获取的值的路径
    - default: 默认值，在键不存在时返回

    返回:
    - 键指示的值，如果不存在则返回默认值
    """
    try:
        # 逐级访问嵌套键的值
        value = data
        for key in keys:
            value = value[key]
        return value
    except (KeyError, TypeError):
        return default


headers = {
    "Referer": "https://m.weibo.cn/p/index?extparam=%E7%A7%A6%E5%B2%9A&containerid=1008084d2c666d52eabaf2ee018a3591028edf&luicode=10000011&lfid=100103type%3D1%26q%3D%E7%A7%A6%E5%B2%9A",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "X-Xsrf-Token": "02748b",
}  # 请求头需携带网页对应接口的Referer和Token
url = "https://m.weibo.cn/api/container/getIndex?extparam=%E7%A7%A6%E5%B2%9A&containerid=1008084d2c666d52eabaf2ee018a3591028edf&luicode=10000011&lfid=100103type%3D1%26q%3D%E7%A7%A6%E5%B2%9A"
# 明星超话对应的js接口
for i in range(1, 2000):
    res = requests.get(url=url, headers=headers).json()
    # log.info(res)
    news = res["data"]["cards"]
    since_id = res["data"]["pageInfo"]["since_id"]
    url = "https://m.weibo.cn/api/container/getIndex?extparam=%E7%A7%A6%E5%B2%9A&containerid=1008084d2c666d52eabaf2ee018a3591028edf&luicode=10000011&lfid=100103type%3D1%26q%3D%E7%A7%A6%E5%B2%9A&since_id={}".format(
        since_id
    )  # 明星超话对应的js接口
    for n in news:
        # log.info(n)
        # 微博具有两种形式的json数据，所有解析方法有两种，取可行的一种
        # try:
        #     detail1 = get_nested_value(n, ['card_group'])[0]
        #     # log.info(detail1)
        #     for detail in detail1['mblog']['pics']:
        #         img_url = detail['large']['url']
        #         if img_url[-1] == 'f':
        #             continue
        #         img_name1 = file_path + '/' + img_url.split('/')[-1]
        #         href_value2 = 'https://image.baidu.com/search/down?url=' + img_url #防微博图床挂了 详情：https://github.com/Semibold/Weibo-Picture-Store/issues/127
        #         r = requests.get(url=href_value2, headers=headers)
        #         with open(img_name1, 'wb') as f:
        #             f.write(r.content)
        #             log.info('{}下载完成'.format(img_name1))
        # except Exception as e:
        #     # log.info(f"An error occurred: {e}")
        #     continue
        try:
            detail2 = get_nested_value(n, ["mblog", "pics"])
            # log.info(detail2)
            for detail in detail2:
                # log.info(detail)
                img_url = detail["large"]["url"]
                # log.info(img_url)
                if img_url[-1] == "f":
                    continue
                img_name1 = file_path + "/" + img_url.split("/")[-1]
                # href_value2 = 'https://image.baidu.com/search/down?url=' + img_url
                href_value2 = (
                    "https://i0.wp.com/" + img_url[8:]
                )  # 防微博图床挂了 详情：https://github.com/Semibold/Weibo-Picture-Store/issues/127
                r = requests.get(url=href_value2, headers=headers)
                with open(img_name1, "wb") as f:
                    f.write(r.content)
                    log.info("{}下载完成".format(img_name1))
        except Exception:
            # log.info(f"An error occurred: {e}")
            continue
