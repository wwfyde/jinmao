import json
from pathlib import Path

from playwright.async_api import Page


async def simulate_user_scroll(page: Page):
    """
    模拟用户滚动
    """
    for _ in range(10):  # 滚动10次，每次滚动1000像素
        await page.mouse.wheel(0, 1000)
        await page.wait_for_timeout(1000)  # 等待页面加载新内容


async def scroll_to_bottom(page: Page):
    """
    通过JavaScript滚动到页面底部
    """
    previous_height = await page.evaluate("document.body.scrollHeight")
    while True:
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(1000)  # 等待页面加载新内容
        new_height = await page.evaluate("document.body.scrollHeight")
        if new_height == previous_height:
            break
        previous_height = new_height


def save_to_json(data: dict, path: Path, filename: str):
    """
    保存数据到json文件
    """
    with open(path.joinpath(filename), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
