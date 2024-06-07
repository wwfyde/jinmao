import asyncio
import random

import redis.asyncio as redis
from playwright.async_api import Playwright, async_playwright

from crawler.config import settings
from crawler.utils import scroll_page
from projects.gap.gap import PLAYWRIGHT_HEADLESS


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
            args=["--start-maximized"],  # 启动时最大化窗口
            # ignore_https_errors=True,  # 忽略HTTPS错误
            # devtools=True,  # 打开开发者工具
        )
    else:
        browser = await chromium.launch(headless=True, devtools=True)
        context = await browser.new_context()

    # 设置全局超时
    context.set_default_timeout(settings.playwright.timeout)
    # context.set_default_timeout(60000)
    # 创建一个新的浏览器上下文，设置视口大小
    # context = await browser.new_context(viewport={"width": 1920, "height": 1080})
    # 在浏览器上下文中打开一个新页面

    # 打开新的页面
    # for base_url in urls:
    page = await context.new_page()
    async with page:
        base_url: str = "https://www.next.co.uk/shop/gender-women-productaffiliation-clothing-0"
        gender = "women"
        base_url = "https://www.next.co.uk/shop/gender-women-productaffiliation-clothing/category-tshirts?p=1#0"
        base_url = "https://www.target.com/c/dresses-women-s-clothing/-/N-5xtcg"
        category = "T-Shirts"
        # 拦截所有图片
        await page.route(
            "**/*",
            lambda route: route.abort() if route.request.resource_type == "image" else route.continue_(),
        )
        await page.goto(base_url)
        b = "/html/body/main/div/div/div[2]/div[4]/div/div[22]/div/div/section/div/div[1]/div[1]/div/div/div[1]/a"
        seletor = "//main/div/div/div[2]/div[4]/div/div/div/div/section/div/div[1]/div[1]/div/div/div[1]/a"
        await page.wait_for_load_state(timeout=60000)
        scroll_pause_time = random.randrange(1500, 2500, 200)
        # await page.wait_for_timeout(1000)
        await scroll_page(page, scroll_pause_time=scroll_pause_time)
        # await page.pause()
        product_locators = page.locator(seletor)
        product_count = await product_locators.count()
        product_urls = []
        for i in range(product_count):
            url = await product_locators.nth(i).get_attribute("href")
            print(url)
            product_urls.append(url)
            # TODO 将 所有url 存入redis, 以持久化
        print(f"一共获取商品数: {len(product_urls)}")

        r = redis.from_url(settings.redis_dsn, decode_responses=True, protocol=3)
        async with r:
            print(await r.get("a"))

            gender = "women"
            result = await r.sadd(f"next:{gender}:{category}", *product_urls)
            print(result)
        # print(products_urls)
        # 将数据持久化到本地
        with open("next_urls.txt", "w") as f:
            for url in product_urls:
                f.write(url + "\n")


async def main():
    # 创建一个playwright对象并将其传递给run函数
    async with async_playwright() as p:
        await run(p)
        ...


# 这是脚本的入口点。
# 它开始执行main函数。
if __name__ == "__main__":
    # 指定本地代理
    # os.environ["http_proxy"] = "http://127.0.0.1:23457"
    # os.environ["https_proxy"] = "http://127.0.0.1:23457"
    # os.environ["all_proxy"] = "socks5://127.0.0.1:23457"
    asyncio.run(main())
