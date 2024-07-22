#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
使用requests请求代理服务器
请求http和https网页均适用
"""

import httpx
from playwright.async_api import Page

from crawler.config import settings

# 隧道域名:端口号
tunnel = "XXX.XXX.com:15818"

# 用户名和密码方式
username = settings.proxy_pool.username
password = settings.proxy_pool.password


async def get_current_ip(page: Page):
    return await page.evaluate(
        "async () => { const response = await fetch('https://api.ipify.org?format=json'); const data = await response.json(); return data.ip; }"
    )


proxy_url = f"http://{settings.proxy_pool.username}:{settings.proxy_pool.password}@{settings.proxy_pool.server.replace('http://', '')}/"

proxies = httpx.Proxy(url=proxy_url)

with httpx.Client(proxies=proxies, timeout=60) as client:
    # r = client.get("https://dev.kdlapi.com/testproxy")
    # print(r.text)
    r = client.get("https://api.ipify.org?format=json")
    print(r.text)

print(get_current_ip())
