"""
第一步，获取分类列表
"""

import asyncio
import json

import httpx
from playwright.async_api import (
    async_playwright,
)

from projects.jcpenney.common import cancel_requests

main_category = "jewelry-and-watches"
main_category = "home-store"
main_category = "young-adult"
main_category = "baby-kids"


async def fetch_category_data():
    """
    获取类别数据
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        await cancel_requests(page)
        await page.goto(f"https://www.jcpenney.com/d/{main_category}")
        await page.wait_for_load_state("domcontentloaded")

        await page.wait_for_timeout(10000)

        elements = await page.query_selector_all(
            'div[data-automation-id="zone-Navigation"] li > a'
        )

        urls = []
        for element in elements:
            url = await element.get_attribute("href")
            sub_category = httpx.URL(url).path.split("/")[-1]
            urls.append((main_category, sub_category, "https://www.jcpenney.com" + url))

        await browser.close()
        print(urls)
        return urls


async def main():
    result = await fetch_category_data()
    result = list(set(result))

    # save to json
    with open(f"projects/jcpenney/category-{main_category}.json", "w") as f:
        json.dump(result, f, indent=4)


if __name__ == "__main__":
    asyncio.run(main())
