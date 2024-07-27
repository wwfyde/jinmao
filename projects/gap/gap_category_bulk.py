import asyncio
import json
from enum import Enum

import httpx
from playwright.async_api import async_playwright, Playwright, Route

from crawler import log
from crawler.config import settings
from projects.gap.gap import parse_category_from_api

# urls = [
#     {
#         "women": [
#             "https://www.gap.com/browse/category.do?cid=1127938&department=136#department=136&pageId=0",
#             "https://www.gap.com/browse/category.do?cid=1127938&department=136#department=136&pageId=1",
#             "https://www.gap.com/browse/category.do?cid=1127938&department=136#department=136&pageId=2",
#             "https://www.gap.com/browse/category.do?cid=1127938&department=136#department=136&pageId=3",
#             "https://www.gap.com/browse/category.do?cid=1127938&department=136#department=136&pageId=4",
#             "https://www.gap.com/browse/category.do?cid=1127938&department=136#department=136&pageId=5",
#             "https://www.gap.com/browse/category.do?cid=1127938&department=136#department=136&pageId=6",
#             "https://www.gap.com/browse/category.do?cid=1127938&department=136#department=136&pageId=7",
#             "https://www.gap.com/browse/category.do?cid=1127938&department=136#department=136&pageId=8",
#         ]
#     },  # 女装 2804
#     {"men.all": "https://www.gap.com/browse/category.do?cid=1127944&department=75"},  # 男装 约1009
# ]
source = "gap"
sub_category = "default"  # 商品子类别
urls = [
    ("men", sub_category, "https://www.gap.com/browse/category.do?cid=1127944&department=75&pageId=0"),
    ("men", sub_category, "https://www.gap.com/browse/category.do?cid=1127944&department=75&pageId=1"),
    ("men", sub_category, "https://www.gap.com/browse/category.do?cid=1127944&department=75&pageId=2"),
    ("men", sub_category, "https://www.gap.com/browse/category.do?cid=1127944&department=75&pageId=3"),
    ("men", sub_category, "https://www.gap.com/browse/category.do?cid=1127944&department=75&pageId=4"),
]
# urls = [
#     # (
#     #     "women",
#     #     sub_category,
#     #     "https://www.gap.com/browse/category.do?cid=1127938&department=136#department=136&pageId=0",
#     # ),
#     # (
#     #     "women",
#     #     sub_category,
#     #     "https://www.gap.com/browse/category.do?cid=1127938&department=136#department=136&pageId=1",
#     # ),
#     # (
#     #     "women",
#     #     sub_category,
#     #     "https://www.gap.com/browse/category.do?cid=1127938&department=136#department=136&pageId=2",
#     # ),
#     # (
#     #     "women",
#     #     sub_category,
#     #     "https://www.gap.com/browse/category.do?cid=1127938&department=136#department=136&pageId=3",
#     # ),
#     # (
#     #     "women",
#     #     sub_category,
#     #     "https://www.gap.com/browse/category.do?cid=1127938&department=136#department=136&pageId=4",
#     # ),
#     (
#         "women",
#         sub_category,
#         "https://www.gap.com/browse/category.do?cid=1127938&department=136#department=136&pageId=5",
#     ),
#     (
#         "women",
#         sub_category,
#         "https://www.gap.com/browse/category.do?cid=1127938&department=136#department=136&pageId=6",
#     ),
#     (
#         "women",
#         sub_category,
#         "https://www.gap.com/browse/category.do?cid=1127938&department=136#department=136&pageId=7",
#     ),
#     (
#         "women",
#         sub_category,
#         "https://www.gap.com/browse/category.do?cid=1127938&department=136#department=136&pageId=8",
#     ),
# ]
# primary_category = "boys"  # 商品主类别
# sub_category = "default"  # 商品子类别
# urls = [("boys", "default", "https://www.gap.com/browse/category.do?cid=6189&department=16")]
# urls = [
#     ("girls", "default", "https://www.gap.com/browse/category.do?cid=1127946&department=48&pageId=0"),
#     ("girls", "default", "https://www.gap.com/browse/category.do?cid=1127946&department=48&pageId=1"),
#     ("girls", "default", "https://www.gap.com/browse/category.do?cid=1127946&department=48&pageId=2"),
#     ("girls", "default", "https://www.gap.com/browse/category.do?cid=1127946&department=48&pageId=3"),
#     ("girls", "default", "https://www.gap.com/browse/category.do?cid=1127946&department=48&pageId=4"),
# ]
PLAYWRIGHT_TIMEOUT: int = settings.playwright.timeout or 1000 * 60
print(PLAYWRIGHT_TIMEOUT)
PLAYWRIGHT_CONCURRENCY: int = settings.playwright.concurrency or 10
PLAYWRIGHT_CONCURRENCY: int = 8
PLAYWRIGHT_HEADLESS: bool = settings.playwright.headless
PLAYWRIGHT_HEADLESS: bool = False
should_use_proxy = True
__doc__ = """
    金茂爬虫, 主要通过按类别爬取和按搜索爬取两种方式
"""


class Category(Enum):
    girls = "14417"


# 这个函数负责启动一个浏览器，打开一个新页面，并在页面上执行操作。
# 它接受一个Playwright对象作为参数。


def get_product_id(url: str) -> str:
    parsed_url = httpx.URL(url)
    return parsed_url.params.get("pid")[:-3]


async def run(playwright: Playwright, urls: list[tuple]) -> None:
    # 从playwright对象中获取chromium浏览器
    chromium = playwright.chromium
    # 指定代理
    # proxy = {"server": "http://127.0.0.1:7890"}
    # 启动chromium浏览器，开启开发者工具，非无头模式
    # browser = await chromium.launch(headless=False, devtools=True)
    user_data_dir = settings.user_data_dir
    if should_use_proxy:
        proxy = {
            "server": settings.proxy_pool.server,
            "username": settings.proxy_pool.username,
            "password": settings.proxy_pool.password,
        }
    else:
        proxy = None
    print(f"使用代理: {proxy}")
    if settings.save_login_state:
        context = await playwright.chromium.launch_persistent_context(
            user_data_dir,
            headless=PLAYWRIGHT_HEADLESS,
            proxy=proxy,
            # headless=False,
            # slow_mo=50,  # 每个操作的延迟时间（毫秒），便于调试
            args=["--start-maximized"],  # 启动时最大化窗口
            # ignore_https_errors=True,  # 忽略HTTPS错误
            # devtools=True,  # 打开开发者工具
        )
    else:
        browser = await chromium.launch(headless=PLAYWRIGHT_HEADLESS, devtools=False,
                                        proxy=proxy
                                        )
        context = await browser.new_context()

    # 设置全局超时
    context.set_default_timeout(settings.playwright.timeout)
    # 创建一个新的浏览器上下文，设置视口大小
    # context = await browser.new_context(viewport={"width": 1920, "height": 1080})
    # 在浏览器上下文中打开一个新页面

    # 打开新的页面
    for index, (main_category, sub_category, base_url) in enumerate(urls):
        page = await context.new_page()
        async with page:
            # 拦截所有图像
            await page.route(
                "**/*",
                lambda route: route.abort() if route.request.resource_type == "image" else route.continue_(),
            )
            products_list = []
            product_count: int = 0
            pages: dict = {}
            sku_index: list = []
            main_route_event = asyncio.Event()

            async def handle_main_route(route: Route):
                """拦截api"""
                request = route.request
                log.info(request.url)
                # api 连接可优化
                if ("cc" and "products" in request.url) and request.resource_type in ("xhr", "fetch"):
                    log.info("获取 headers和Cookie")
                    log.info(request.headers)
                    # 获取cookie
                    cookies = await context.cookies(request.url)
                    cookie_str = "; ".join([f"{cookie['name']}={cookie['value']}" for cookie in cookies])

                    response = await route.fetch()
                    log.info(response.url)
                    # log.info(f"接口原始数据: {await response.text()}")
                    json_dict = await response.json()
                    # log.info(f"类别接口数据: \n{json_dict}")
                    categories_dir = settings.data_dir.joinpath(source)
                    categories_dir.mkdir(parents=True, exist_ok=True)

                    with open(
                            f"{categories_dir}/category-{main_category}-{main_category}-{index:03d}.json", "w"
                    ) as f:
                        f.write(json.dumps(json_dict))

                    # TODO  获取products by categories
                    log.info(f"从类别[category]页面: {main_category}-{sub_category}获取商品数据")
                    products, _product_count, _pages, _sku_index = await parse_category_from_api(
                        json_dict,
                        page,
                        gender=main_category,
                        source=source,
                        main_category=main_category,
                        sub_category=sub_category,
                    )
                    nonlocal product_count
                    product_count = _product_count
                    nonlocal pages
                    pages = _pages
                    nonlocal sku_index
                    sku_index = _sku_index

                    products_list.extend(products)

                    # log.info(f"序列化后数据: {products}")
                    main_route_event.set()
                await route.continue_()

            # 拦截 API
            await page.route("**/api.gap.com/**", handle_main_route)

            # TODO 指定url
            # 导航到指定的URL
            await page.goto(base_url, timeout=PLAYWRIGHT_TIMEOUT)
            log.info(f"打开类别[category]页面: {base_url}")
            # 其他操作...
            # 暂停执行
            # await page.pause()
            await page.wait_for_timeout(3000)
            await page.wait_for_load_state("load")  # 等待页面加载

            # TODO 不再滚动
            # scroll_pause_time = random.randrange(1000, 2500, 500)
            # # await page.wait_for_timeout(1000)
            # await scroll_page(page, scroll_pause_time=scroll_pause_time)
            # # await page.pause()
            # await page.wait_for_load_state("load")  # 等待页面加载完成
            # log.info(f"页面加载完成后页面高度{await page.evaluate('document.body.scrollHeight')}")
            #
            # element = page.get_by_label("items in the product grid")
            #
            # if not element:
            #     log.info("未获取到选择器")
            #     await page.pause()
            # text = await element.first.text_content()
            # items: int = int(re.match(r"(\d+)", text).group(1)) if text else 0
            # log.info(f"共发现{items}件商品")
            # # await page.pause()
            # # 提取所有商品链接
            # main_content = await page.content()
            # main_tree = etree.HTML(main_content)
            # # log.info("从route获取到的数据: ", results)

            # 等待路由事件完成
            await main_route_event.wait()

            # log.info(f"拦截路由更新: {products_list}")
            log.info(f"拦截路由更新: {product_count}")
            log.info(f"拦截路由更新: {pages}")
            log.info(f"拦截路由更新: 数量{len(sku_index)},  {sku_index}")

            # pdp_urls = main_tree.xpath("//*[@id='faceted-grid']/section/div/div/div/div[1]/a/@href")
            # log.info(f"获取到{len(pdp_urls)}个商品链接")

            # break
        # 商品摘取完毕
    # 关闭浏览器context
    log.info("商品抓取完毕, 关闭浏览器")
    await context.close()


# 这个函数是脚本的主入口点。
# 它创建一个playwright对象，并将其传递给run函数。
async def main():
    # 创建一个playwright对象并将其传递给run函数
    async with async_playwright() as p:
        await run(p, urls)
        ...


# 这是脚本的入口点。
# 它开始执行main函数。
if __name__ == "__main__":
    # 指定本地代理
    asyncio.run(main())
