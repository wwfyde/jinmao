import asyncio

import httpx
import redis.asyncio as redis
from playwright.async_api import Playwright, async_playwright

from crawler import log
from crawler.config import settings
from projects.gap.gap import open_pdp_page

PLAYWRIGHT_TIMEOUT: int = settings.playwright.timeout or 1000 * 60
print(PLAYWRIGHT_TIMEOUT)
PLAYWRIGHT_CONCURRENCY: int = settings.playwright.concurrency or 10
PLAYWRIGHT_CONCURRENCY: int = 8
PLAYWRIGHT_HEADLESS: bool = settings.playwright.headless


async def run(playwright: Playwright) -> None:
    # 从playwright对象中获取chromium浏览器
    chromium = playwright.chromium
    # 指定代理
    # proxy = {"server": "http://127.0.0.1:7890"}
    # 启动chromium浏览器，开启开发者工具，非无头模式
    # browser = await chromium.launch(headless=False, devtools=True)
    user_data_dir = settings.user_data_dir
    if settings.save_login_state:
        context = await playwright.chromium.launch_persistent_context(
            user_data_dir,
            headless=PLAYWRIGHT_HEADLESS,
            # headless=False,
            # slow_mo=50,  # 每个操作的延迟时间（毫秒），便于调试
            # args=["--start-maximized"],  # 启动时最大化窗口
            # ignore_https_errors=True,  # 忽略HTTPS错误
            # devtools=True,  # 打开开发者工具
        )
    else:
        browser = await chromium.launch(headless=True, devtools=True)
        context = await browser.new_context()

    # 设置全局超时
    context.set_default_timeout(settings.playwright.timeout)
    r = redis.from_url(settings.redis_dsn, decode_responses=True, protocol=3)
    gender = "*"
    async with r:
        keys: list[str] = await r.keys(f"gap_search:{gender}:*")
        pass
    sku_index = []
    for key in keys:
        _, gender, product_id = key.split(":")
        url = await r.get(key)
        sku_id = httpx.URL(url).params.get("pid")
        sku_index.append((product_id, sku_id))
    tasks = []
    semaphore = asyncio.Semaphore(PLAYWRIGHT_CONCURRENCY)  # 设置并发请求数限制为10

    for product_id, sku_id in sku_index:
        tasks.append(
            open_pdp_page(
                context,
                semaphore,
                product_id,
                sku_id,
                primary_category=gender,
                sub_category="default",
                source="gap",
            )
        )
    result = await asyncio.gather(*tasks)
    log.info(f"获取到的商品sku_id 列表: {result}")
    log.info("商品抓取完毕, 关闭浏览器")
    # await context.close()


async def main():
    # 创建一个playwright对象并将其传递给run函数
    async with async_playwright() as p:
        await run(p)
        ...


if __name__ == "__main__":
    asyncio.run(main())
