__doc__ = """
按关键词获取商品列表
"""

import asyncio
import random

import aiofiles
import httpx
import redis.asyncio as redis
from playwright.async_api import Playwright, async_playwright

from crawler.config import settings
from crawler.deps import get_logger
from crawler.utils import scroll_page

log = get_logger("next")
log.info(f"日志配置成功, 日志器: {log.name}")

# log.debug(f"{PLAYWRIGHT_TIMEOUT=}")
settings.save_login_state = False
settings.playwright.headless = False


keyword = 'pyjamas'
base_url = f'https://www.next.co.uk/search?w={keyword}'


def parse_url(url: str) -> tuple[str, str]:
    """
    解析url, 返回类别和类别url
    :param url:
    :return:
    """
    url = httpx.URL(url)
    path = url.path
    product_id = path.split('/')[-2].upper()
    sku_id = path.split('/')[-1].upper()

    return product_id, sku_id

async def run(playwright: Playwright) -> None:
    # 从playwright对象中获取chromium浏览器
    chromium = playwright.chromium
    # 指定代理
    # proxy = {"server": "http://127.0.0.1:7890"}
    # 启动chromium浏览器，开启开发者工具，非无头模式
    # browser = await chromium.launch(headless=False, devtools=True)
    user_data_dir = settings.user_data_dir
    proxy = {
        "server": settings.proxy_pool.server,
        "username": settings.proxy_pool.username,
        "password": settings.proxy_pool.password,
    }
    proxy = None
    if settings.save_login_state:
        context = await playwright.chromium.launch_persistent_context(
            user_data_dir,
            # headless=True,
            proxy=proxy,
            headless=settings.playwright.headless,
            # slow_mo=50,  # 每个操作的延迟时间（毫秒），便于调试
            args=["--start-maximized"],  # 启动时最大化窗口
            # ignore_https_errors=True,  # 忽略HTTPS错误
            # devtools=True,  # 打开开发者工具
        )
    else:
        browser = await chromium.launch(
            headless=settings.playwright.headless,
            # devtools=True,
            proxy=proxy)
        context = await browser.new_context()

    # 设置全局超时
    context.set_default_timeout(settings.playwright.timeout)
    # context.set_default_timeout(60000)
    # 创建一个新的浏览器上下文，设置视口大小
    # context = await browser.new_context(viewport={"width": 1920, "height": 1080})
    # 在浏览器上下文中打开一个新页面

    # 打开新的页面
    # for base_url in urls:

    # TODO 修复 base_url
    r = redis.from_url(settings.redis_dsn, decode_responses=True, protocol=3)

    total = 18880
    page_size = 12
    page_count = (total + page_size - 1) // page_size

    # category = category_url.split("/")[-1].split("-")[-1]
    segment = 40  # TODO 控制每次滚动的数量
    # segment = 10  # 控制每次滚动的数量
    times = (page_count + segment - 1) // segment
    print(f"{times=}")
    log.debug(f"分页{segment=}, {times=}")
    all_counter = 0
    file_path = f"products_{keyword}.txt"
    for j in range(0, times):
        log.debug(f"开始第{j + 1}轮 处理, 共 {times} 轮")
        next_base_url = base_url + f"&p={j * segment + 1}"

        page = await context.new_page()
        async with page:
            # category = base_url.split("/")[-1].split("-")[-1]
            # 拦截所有图片
            await page.route(
                "**/*",
                lambda route: route.abort() if route.request.resource_type == "image" else route.continue_(),
            )
            log.debug(f"打开页面: {next_base_url}")
            await page.goto(next_base_url)
            await page.wait_for_load_state(timeout=60000)
            await page.wait_for_timeout(5000)
            scroll_pause_time = random.randrange(1000, 1800, 200)
            # await page.wait_for_timeout(1000)
            log.debug("开始滚动页面")
            await scroll_page(page, scroll_pause_time=scroll_pause_time, source="next", page_size=segment)
            # await page.pause()
            product_locators = page.locator('[data-testid="plp-product-grid-item"]')
            product_count = await product_locators.count()
            log.info(f"locators数量: {product_count}")
            product_urls = []
            for i in range(product_count):
                try:
                    url = await product_locators.nth(i).locator(
                        "section > div > div:nth-child(2) > a").get_attribute(
                        "href", timeout=10000)
                    # log.debug(f"抓取到商品url: {url}")
                    product_id, sku_id = parse_url(url)
                    sequence = i + 1 + all_counter
                    # print(f"{product_id=}, {sku_id=}, {sequence=}")
                    async with aiofiles.open(file_path, mode='a') as f:
                        await f.write(f"{product_id}, {sku_id}, {sequence}\n")
                    # TODO 获取商品id
                    # product_urls.append(url)
                except Exception as exc:
                    log.error(f"获取商品url失败: {exc}")
                    pass
            all_counter += product_count  # 计算总数

            print(f"一共获取商品数: {len(product_urls)}")

            print(page.url)
            # await page.pause()
            log.debug(f"第{j + 1}轮: {page.url}")
            await page.wait_for_timeout(2000)
    log.debug(f"完成 对 {keyword} 类别的商品索引建立")


    await context.close()


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
