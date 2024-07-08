"""
第二步
获取商品列表信息
"""

import json
import os
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse
from loguru import logger
from playwright.async_api import (
    async_playwright,
)

from projects.jcpenney.common import cancel_requests

CACHE_PATH = "projects/jcpenney/cache.json"


def update_url_page(url: str, next_page_num: int) -> str:
    """替换翻页的 url"""
    parsed_url = urlparse(url)
    query = parse_qs(parsed_url.query)

    query["page"] = [next_page_num]  # 参数值应为列表形式以适应 urlencode 方法
    new_query_string = urlencode(query, doseq=True)
    new_url = parsed_url._replace(query=new_query_string)
    updated_url = urlunparse(new_url)

    return updated_url


async def handle_items_url(page, json_file_path: str):
    """获取并去重商品列表的 url"""
    elements = await page.query_selector_all(
        "div#gallery-product-list div.list-body li div.gallery + a"
    )
    urls = [
        "https://www.jcpenney.com" + await element.get_attribute("href")
        for element in elements
    ]
    urls = list(set(urls))
    with open(json_file_path, "w") as f:
        json.dump(urls, f, indent=4)


async def fetch_page(page, filename: str, page_num: int, last_page_num: str):
    """
    保存item数据到json
    """

    folder = f"projects/jcpenney/data/{filename}"
    json_filename = f"{filename}_{page_num}.json"
    os.makedirs(folder, exist_ok=True)

    # 处理已经抓取过的内容
    if os.path.exists(f"{folder}/{json_filename}"):
        logger.debug(f"已经抓取过: {folder}/{json_filename}")
        # 查看下一个未抓取的内容
        next_json_filename: str = f"{filename}_{page_num + 1}.json"
        next_json_path: str = os.path.join(folder, next_json_filename)

        while os.path.exists(next_json_path) and page_num < int(last_page_num):
            page_num += 1
            logger.debug(
                f"已经抓取过:  {folder}/{json_filename}, 查看下一个未抓取的内容: {next_json_path}"
            )
            next_json_filename = f"{filename}_{page_num + 1}.json"
            next_json_path = os.path.join(folder, next_json_filename)

        if page_num > int(last_page_num) and os.path.exists(next_json_path):
            logger.debug(f"已达到最大页数: {page_num}")
            return last_page_num + 1

        await page.wait_for_timeout(10000)
        return page_num

    if page_num > 1:
        await page.wait_for_timeout(10000)

    logger.info(f"fetching page {page_num}")

    json_file_path: str = f"{folder}/{json_filename}"
    await handle_items_url(page, json_file_path)

    await page.wait_for_timeout(3000)
    return page_num


async def fetch_item_list(url: str):
    logger.info("=" * 50)
    logger.info(f"开始任务 - 首页地址：{url}")
    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(headless=False, timeout=60000)
            context = await browser.new_context(storage_state=CACHE_PATH)
            page = await context.new_page()
            await cancel_requests(page)

            # 想拿到 women_tops 的string
            file_url = url.replace("https://www.jcpenney.com/g/", "").split("?")[0]
            filename = file_url.replace("/", "_")
            await page.goto(url)
            await page.wait_for_timeout(10000)

            # 获取总页数
            last_page = await page.query_selector(
                "div.pagination-container > div >div:last-of-type"
            )
            last_page_num = await last_page.inner_text()
            logger.info(f"一共: {last_page_num} 页内容")

            # TODO 优化翻页逻辑
            page_num = 1
            next_page_num = await fetch_page(page, filename, page_num, last_page_num)
            if next_page_num > int(last_page_num):
                await browser.close()
                return

            next_button = await page.query_selector("//button[contains(., 'Next')]")
            while next_button:
                try:
                    next_page_num += 1
                    if next_page_num > int(last_page_num):
                        await browser.close()
                        logger.info("抓取完毕")
                        return

                    await next_button.scroll_into_view_if_needed()

                    next_url = update_url_page(url, next_page_num)
                    logger.info(f"跳转到 {next_url}")
                    await page.goto(next_url, timeout=60000)
                    # await next_button.click(timeout=60000)
                    next_page_num = await fetch_page(
                        page, filename, next_page_num, last_page_num
                    )
                except:
                    await page.reload()
                    await page.wait_for_timeout(10000)
                    pass
                next_button = await page.query_selector("//button[contains(., 'Next')]")
        except Exception as e:
            logger.error(f"Error: {e}")
        finally:
            await browser.close()


def clean():
    """
    清洗数据中的重复内容
    """
    for folder in Path("projects/jcpenney/data").glob("*"):
        print(folder)
        data = []
        for f in folder.glob("*.json"):
            print(f)
            with open(f, "r", encoding="utf-8") as file:
                data.extend(json.load(file))

        Path(f"projects/jcpenney/clean_data").mkdir(exist_ok=True, parents=True)
        with open(
            f"projects/jcpenney/clean_data/{folder.stem}.json", "w", encoding="utf-8"
        ) as file:
            data = list(set(data))
            json.dump(data, file, indent=4)


async def main():
    # read json

    with open("projects/jcpenney/category.json", "r") as f:
        urls = json.load(f)

    for url in urls:
        await fetch_item_list(url)
