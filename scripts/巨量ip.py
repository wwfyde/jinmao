#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
使用requests请求代理服务器
请求http和https网页均适用
"""

import asyncio
import random

import httpx
import requests

page_url = "https://www.google.com"  # 要访问的目标网页

# API接口，返回格式为json
api_url = "http://v2.api.juliangip.com/dynamic/getips?auto_white=1&num=1&pt=1&result_type=text&split=1&trade_no=1690449746818529&sign=ec3f4eca8e63a24dfacb17745da4871e"  # API接口

# API接口返回的proxy_list
proxy_list = requests.get(api_url).text
print(proxy_list)

# 用户名密码认证(动态代理/独享代理)
username = "18580955634"
password = "xQlOFPal"


async def fetch(url):
    print(f"http://{username}:{password}@{random.choice([proxy_list])}")
    proxies = {
        # "http://": f"http://{username}:{password}@{random.choice(proxy_list)}",
        "http://": f"http://{username}:{password}@{random.choice([proxy_list])}",
        "https://": f"http://{username}:{password}@{random.choice([proxy_list])}",
    }
    async with httpx.AsyncClient(
        proxies=proxies,
        timeout=60,
    ) as client:
        resp = await client.get(url)
        print(f"status_code: {resp.status_code}, content: {resp.content}")


async def run():
    # 异步发出5次请求
    tasks = [fetch(page_url) for _ in range(5)]
    results = asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(fetch(page_url))
