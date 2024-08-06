__doc__ = """
# 按类别搜索
DOM
API示例:
https://search-api.jcpenney.com/v1/search-service/g/women/skirts?productGridView=medium&id=cat100250097&responseType=organic
首先, 获取类别信息, 然后逐一获取每个类别下面的商品信息

"""

import asyncio

import os

import redis.asyncio as redis
from concurrent.futures import ProcessPoolExecutor
from playwright.async_api import async_playwright

from crawler.config import settings
from crawler.deps import get_logger
from projects.jcpenney.common import cancel_requests

log = get_logger("jcpenney")


async def run(main_category: str, sub_category: str, url: str):
    """
    获取类别数据
    """
    r = redis.from_url(settings.redis_dsn, decode_responses=True, protocol=3)

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=False)
        page = await browser.new_page()
        await cancel_requests(page)
        log.info(f"开始任务: {main_category=}, {sub_category=}, 首页地址：{url}")

        await page.goto(url)

        await page.wait_for_load_state("domcontentloaded")

        await page.wait_for_timeout(10000)

        # 获取最大页数
        last_page = page.locator(
            "div.pagination-container > div >div:last-of-type"
        )
        max_page_num = await last_page.inner_text()
        print(f"最大页数: {max_page_num}")

        locators = page.locator("div#gallery-product-list div.list-body li div.gallery + a")
        elements = await locators.element_handles()

        urls = [await element.get_attribute("href") for element in elements]

        print(urls)

        await browser.close()

        # 根据列表逐一获取商品信息


async def main():
    loop = asyncio.get_running_loop()
    num_processes = os.cpu_count() // 2
    log.info(f"CPU核心数: {os.cpu_count()}, 进程数: {num_processes}")
    categories = [

        ("boys", "shirts",
         "https://www.jcpenney.com/g/men/mens-shirts?id=cat100240025&cm_re=ZJ-_-DEPARTMENT-MEN-_-VN-_-CATEGORIES-_-SHIRTS_1"),
    ]
    with ProcessPoolExecutor(max_workers=num_processes) as executor:
        tasks = [loop.run_in_executor(executor, async_runner, main_category, sub_category, url) for
                 main_category, sub_category, url in categories]
        task_results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in task_results:
            if isinstance(result, Exception):
                log.error(f"{result}")


def async_runner(main_category: str, sub_category: str, url: str):
    asyncio.run(run(main_category, sub_category, url))


if __name__ == "__main__":
    asyncio.run(main())
