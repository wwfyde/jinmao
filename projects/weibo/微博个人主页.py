import os
import platform
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import requests

# import httpx

# file_path = r'E:\收集图片\井柏然超话'#文件路径

base_url = 'https://m.weibo.cn/u/3606929931?t=&luicode=10000011&lfid=100103type=1&q=檀健次'


# if not os.path.exists(file_path):
#     os.makedirs(file_path)
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


def worker(url: str, storage_name: str = 'default', headers: dict = None,
           base_path: Path = Path.home().joinpath('temp')):
    print(f"第正在下载 [{storage_name}] 的图片")

    file_path = base_path.joinpath(storage_name)
    file_path.mkdir(parents=True, exist_ok=True)
    # 明星超话对应的js接口
    for i in range(1, 2000):
        res = requests.get(url=url, headers=headers, timeout=10).json()
        # print(res)
        news = res['data']['cards']
        # print(news)
        since_id = res['data']['cardlistInfo']['since_id']
        # print(since_id)

        # httpx.URL()
        url = f"{url}&since_id={since_id}"  # 明星超话对应的js接口
        for n in news:
            # print(n)
            # 微博具有两种形式的json数据，所有解析方法有两种，取可行的一种
            # try:
            #     detail1 = get_nested_value(n, ['card_group'])[0]
            #     print(detail1)
            #     for detail in detail1['mblog']['pics']:
            #         img_url = detail['large']['url']
            #         if img_url[-1] == 'f':
            #             continue
            #         img_name1 = file_path + '/' + img_url.split('/')[-1]
            #         href_value2 = 'https://image.baidu.com/search/down?url=' + img_url #防微博图床挂了 详情：https://github.com/Semibold/Weibo-Picture-Store/issues/127
            #         r = requests.get(url=href_value2, headers=headers)
            #         with open(img_name1, 'wb') as f:
            #             f.write(r.content)
            #             print('{}下载完成'.format(img_name1))
            # except Exception as e:
            #     # print(f"An error occurred: {e}")
            #     continue
            try:
                detail2 = get_nested_value(n, ['mblog', 'pics'])
                # print(detail2)
                for detail in detail2:
                    # print(detail)
                    img_url = detail['large']['url']
                    # print(img_url)
                    if img_url[-1] == 'f':
                        continue
                    img_name1 = str(file_path) + '/' + img_url.split('/')[-1]
                    # href_value2 = 'https://image.baidu.com/search/down?url=' + img_url
                    href_value2 = 'https://i0.wp.com/' + img_url[
                                                         8:]  # 防微博图床挂了 详情：https://github.com/Semibold/Weibo-Picture-Store/issues/127
                    r = requests.get(url=href_value2, headers=headers)
                    with open(img_name1, 'wb') as f:
                        f.write(r.content)
                        print('{}下载完成'.format(img_name1))
            except Exception as e:
                # print(f"An error occurred: {e}")
                print(f"抓取时出现异常, {e=}")
                continue


if __name__ == '__main__':

    os_type = platform.system()
    print(os_type)
    if os_type == 'Windows':
        base_path = Path('E:/收集图片')  # 基础图片路径
    elif os_type == 'Darwin':
        base_path = Path.home().joinpath('图片收集')  # 基础图片路径
    else:
        base_path = Path.home().joinpath('图片收集')
    max_workers = os.cpu_count()
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        headers = {
            'Referer': 'https://m.weibo.cn/u/1165631310?t=0&luicode=10000011&lfid=100103type%3D1%26q%3D%E5%91%A8%E6%9D%B0%E4%BC%A6',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.1 Safari/605.1.15',
            'X-Xsrf-Token': '510d6c',
        }  # 请求头需携带网页对应接口的Referer和Token

        # TODO 修改这里
        tasks = [
            dict(
                url='https://m.weibo.cn/api/container/getIndex?luicode=10000011&lfid=100103type%3D1%26q%3D%E4%BA%95%E6%9F%8F%E7%84%B6&type=uid&value=3228169532&containerid=1076033228169532',
                storage_name='井柏然'
            ),
            dict(
                url='https://m.weibo.cn/api/container/getIndex?luicode=10000011&lfid=100103type%3D1%26q%3D%E4%BA%95%E6%9F%8F%E7%84%B6&type=uid&value=3228169532&containerid=1076033228169532',
                storage_name='井柏然2'
            ),
        ]
        futures = [
            executor.submit(worker, item.get('url'), item.get('storage_name'), headers=headers, base_path=base_path)
            for item in tasks
        ]
        for future in futures:
            storage_name = future.result()
            print(f"完成下载 [{storage_name}] 的图片")
        # for item in tasks:
        #     storage_name = item.get('storage_name')
        #     future = executor.submit(worker, item.get('url'), item.get('storage_name'), headers=headers,
        #                              base_path=base_path)
        #     print(future.result())
