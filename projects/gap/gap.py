import asyncio
import json
import random
from enum import Enum
from pathlib import Path

import httpx
from lxml import etree
from playwright.async_api import async_playwright, Playwright, Page, Route, BrowserContext

from crawler import log
from crawler.config import settings
from crawler.store import save_review_data, save_sku_data, save_product_data

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
# primary_category = "women"  # 商品主类别
# sub_category = "default"  # 商品子类别
# urls = [
#     (
#         primary_category,
#         sub_category,
#         "https://www.gap.com/browse/category.do?cid=1127938&department=136#department=136&pageId=0",
#     ),
#     (
#         primary_category,
#         sub_category,
#         "https://www.gap.com/browse/category.do?cid=1127938&department=136#department=136&pageId=1",
#     ),
#     (
#         primary_category,
#         sub_category,
#         "https://www.gap.com/browse/category.do?cid=1127938&department=136#department=136&pageId=2",
#     ),
#     (
#         primary_category,
#         sub_category,
#         "https://www.gap.com/browse/category.do?cid=1127938&department=136#department=136&pageId=3",
#     ),
#     (
#         primary_category,
#         sub_category,
#         "https://www.gap.com/browse/category.do?cid=1127938&department=136#department=136&pageId=4",
#     ),
#     (
#         primary_category,
#         sub_category,
#         "https://www.gap.com/browse/category.do?cid=1127938&department=136#department=136&pageId=5",
#     ),
#     (
#         primary_category,
#         sub_category,
#         "https://www.gap.com/browse/category.do?cid=1127938&department=136#department=136&pageId=6",
#     ),
#     (
#         primary_category,
#         sub_category,
#         "https://www.gap.com/browse/category.do?cid=1127938&department=136#department=136&pageId=7",
#     ),
#     (
#         primary_category,
#         sub_category,
#         "https://www.gap.com/browse/category.do?cid=1127938&department=136#department=136&pageId=8",
#     ),
# ]
# primary_category = "boys"  # 商品主类别
# sub_category = "default"  # 商品子类别
urls = [("boys", "default", "https://www.gap.com/browse/category.do?cid=6189&department=16")]
PLAYWRIGHT_TIMEOUT: int = settings.playwright.timeout or 1000 * 60
print(PLAYWRIGHT_TIMEOUT)
PLAYWRIGHT_CONCURRENCY: int = settings.playwright.concurrency or 10
PLAYWRIGHT_HEADLESS: bool = settings.playwright.headless
# PLAYWRIGHT_HEADLESS: bool = True

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
    # 创建一个新的浏览器上下文，设置视口大小
    # context = await browser.new_context(viewport={"width": 1920, "height": 1080})
    # 在浏览器上下文中打开一个新页面

    # 打开新的页面
    for index, (primary_category, sub_category, base_url) in enumerate(urls):
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
                        f"{categories_dir}/category-{primary_category}-{primary_category}-{index:03d}.json", "w"
                    ) as f:
                        f.write(json.dumps(json_dict))

                    # TODO  获取products by categories
                    log.info(f"从类别[category]页面: {primary_category}-{sub_category}获取商品数据")
                    products, _product_count, _pages, _sku_index = await parse_category_from_api(
                        json_dict,
                        page,
                        gender=primary_category,
                        source=source,
                        primary_category=primary_category,
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
            # # log.info("从route获取到的数据: ", result)

            # 等待路由事件完成
            await main_route_event.wait()

            log.info(f"拦截路由更新: {products_list}")
            log.info(f"拦截路由更新: {product_count}")
            log.info(f"拦截路由更新: {pages}")
            log.info(f"拦截路由更新: 数量{len(sku_index)},  {sku_index}")

            # pdp_urls = main_tree.xpath("//*[@id='faceted-grid']/section/div/div/div/div[1]/a/@href")
            # log.info(f"获取到{len(pdp_urls)}个商品链接")

            # 并发抓取商品
            semaphore = asyncio.Semaphore(PLAYWRIGHT_CONCURRENCY)  # 设置并发请求数限制为10
            log.debug(f"并发请求数: {PLAYWRIGHT_CONCURRENCY}")
            tasks = []
            for product_id, sku_id in sku_index:
                tasks.append(
                    open_pdp_page(
                        context,
                        semaphore,
                        product_id,
                        sku_id,
                        primary_category=primary_category,
                        sub_category=sub_category,
                        source=source,
                    )
                )

            result = await asyncio.gather(*tasks)
            log.info(f"获取到的商品sku_id 列表: {result}")

            # break
        # 商品摘取完毕
    # 关闭浏览器context
    log.info("商品抓取完毕, 关闭浏览器")
    await context.close()


async def open_pdp_page(
    context: BrowserContext,
    semaphore: asyncio.Semaphore,
    product_id: str,
    sku_id: str,
    *,
    source: str,
    primary_category: str,
    sub_category: str,
):
    async with semaphore:
        # product_detail_page 产品详情页
        pdp_url = f"https://www.gap.com/browse/product.do?pid={sku_id}#pdp-page-content"

        # sku_id = int(httpx.URL(pdp_url).params.get("pid", 0))
        log.info(f"{sku_id=}")
        sub_page = await context.new_page()
        sub_page.set_default_timeout(PLAYWRIGHT_TIMEOUT)

        async with sub_page:
            # await sub_page.goto(pdp_url)
            await sub_page.route(
                "**/*",
                lambda route: route.abort() if route.request.resource_type == "image" else route.continue_(),
            )
            route_event = asyncio.Event()

            async def handle_route(route: Route):
                """
                拦截评论路由并获取评论信息
                """
                request = route.request

                if "/reviews" in request.url:
                    response = await route.fetch()
                    json_dict = await response.json()
                    # 将评论信息保存到文件 注意分页
                    product_raw_dir = settings.data_dir.joinpath(
                        source, primary_category, sub_category, product_id, "raw_data"
                    )
                    product_raw_dir.mkdir(parents=True, exist_ok=True)

                    with open(f"{product_raw_dir}/review-{product_id}-00.json", "w") as f:
                        f.write(json.dumps(json_dict, indent=4, ensure_ascii=False))

                    # TODO  获取评论信息
                    reviews, total_count = parse_reviews_from_api(json_dict)
                    log.info(f"预期评论数{total_count}, {len(reviews)}")
                    page_size = 25
                    total_pages = (total_count + page_size - 1) // page_size
                    log.info(f"总页数{total_pages}")

                    semaphore = asyncio.Semaphore(10)  # 设置并发请求数限制为5
                    tasks = []
                    for i in range(1, total_pages + 1):
                        review_url = (
                            request.url
                            + "&sort=Newest"
                            + f"&paging.from={10 + (i - 1) * page_size}"
                            + f"&paging.size={page_size}"
                            + "&filters=&search=&sort=Newest&image_only=false"
                        )
                        tasks.append(
                            fetch_reviews(
                                semaphore,
                                review_url,
                                request.headers,
                                product_id=product_id,
                                index=i,
                                primary_category=primary_category,
                                sub_category=sub_category,
                            )
                        )

                    new_reviews = await asyncio.gather(*tasks)
                    for review in new_reviews:
                        reviews.extend(review)

                    log.info(f"实际评论数{len(reviews)}")
                    # 存储评论信息
                    product_store_dir = settings.data_dir.joinpath(source, primary_category, sub_category, product_id)
                    product_store_dir.mkdir(parents=True, exist_ok=True)
                    with open(f"{product_store_dir}/review-{product_id}.json", "w") as f:
                        log.info(f"存储评论到文件{product_store_dir}/review-{product_id}.json")
                        f.write(json.dumps(reviews, indent=4, ensure_ascii=False))
                    # 将评论保存到数据库

                    save_review_data(reviews)
                    # # 聚合评论
                    # product_store_dir2 = settings.data_dir.joinpath(source, "reviews")
                    # product_store_dir2.mkdir(parents=True, exist_ok=True)
                    # with open(f"{product_store_dir2}/review-{product_id}.json", "w") as f:
                    #     log.info(f"存储评论到文件{product_store_dir}/review-{product_id}.json")
                    #     f.write(json.dumps(reviews, indent=4, ensure_ascii=False))
                    route_event.set()
                    # log.info("获取评论信息")
                    # with open(f"{settings.project_dir.joinpath('data', 'product_info')}/data-.json", "w") as f:
                    #     f.write(json.dumps(json_dict))
                    # pass
                # if "api" in request.pdp_url or "service" in request.pdp_url:
                #
                #     log.info(f"API Request URL: {request.pdp_url}")
                await route.continue_()

            await sub_page.route("**/display.powerreviews.com/**", handle_route)

            # 进入新页面
            await sub_page.goto(pdp_url, timeout=PLAYWRIGHT_TIMEOUT)
            # sub_page.on("request", lambda request: log.info(f"Request: {request.pdp_url}"))
            # sub_page.on("response", lambda response: log.info(f"Request: {response.pdp_url}"))

            # 拦截所有api pdp_url
            await sub_page.wait_for_timeout(5 * 1000)
            scroll_pause_time = random.randrange(1500, 2500, 500)
            # await page.wait_for_timeout(1000)
            await scroll_page(sub_page, scroll_pause_time=scroll_pause_time)
            # await page.wait_for_load_state("load")
            content = await sub_page.content()
            raw_data_dir = settings.data_dir.joinpath(source, primary_category, sub_category, product_id, "raw_data")
            raw_data_dir.mkdir(parents=True, exist_ok=True)
            with open(f"{raw_data_dir}/pdp-{product_id}.html", "w") as f:
                f.write(content)
            # 获取产品详情页(pdp)信息
            dom_pdp_info = await parse_sku_from_dom_content(
                content, product_id=product_id, sku_id=str(sku_id), source=source, product_url=pdp_url
            )
            # TODO 更新信息到数据库和json文件 或者等从接口拿取后统一写入
            model_image_urls = dom_pdp_info.get("model_image_urls", [])
            print(
                f"{model_image_urls=}",
            )
            base_url = "https://www.gap.com"
            image_tasks = []
            semaphore = asyncio.Semaphore(10)  # 设置并发请求数限制为10
            sku_dir = settings.data_dir.joinpath(source, primary_category, sub_category, str(product_id), str(sku_id))
            sku_model_dir = sku_dir.joinpath("model")
            sku_model_dir.mkdir(parents=True, exist_ok=True)
            for index, url in enumerate(model_image_urls):
                url = url.replace("https://www.gap.com", "")
                image_tasks.append(
                    fetch_images(
                        semaphore,
                        base_url + url,
                        {},
                        file_path=sku_model_dir.joinpath(f"model-{(index + 1):02d}-{url.split('/')[-1]}"),
                    )
                )

            await asyncio.gather(*image_tasks)

            # await sub_page.get_by_label("close email sign up modal").click()
            log.info(f"进入商品页面: {pdp_url}")
            await sub_page.wait_for_load_state("domcontentloaded")
            # await sub_page.wait_for_timeout(60000)
            # await sub_page.wait_for_selector("h1")

            # 商品标题
            product_title = await sub_page.locator("#buy-box > div > h1").text_content()
            # 商品id, pid
            log.info(f"商品: {sku_id}, 标题: {product_title}")

            await route_event.wait()
            log.debug("路由执行完毕")
            await asyncio.sleep(random.randrange(5, 12, 3))
        # 返回sku_id 以标记任务成功
        log.info(f"任务完成: {sku_id}")
        return sku_id


async def parse_sku_from_api(sku: dict, sku_id: int) -> dict | None:
    """
    获取商品信息
    """
    # to
    pdm_item: dict | None = sku.get("pdp_item", None)
    if not pdm_item:
        return None
    category = sku.get("pdp_item", "")
    sku_url: str = pdm_item.get("item_url")
    if sku_url:
        sku_id = httpx.URL(sku_url).params.get("pid", "")
    else:
        sku_id = None
    product_id = pdm_item.get("uni").split("||")[0]
    image_url = pdm_item.get("image_url")
    images: list = pdm_item.get("details").get("original_images") if pdm_item.get("details") else None
    title = pdm_item.get("title")

    return dict(
        sku_id=sku_id,
        product_id=product_id,
        category=category,
        sku_url=sku_url,
        image_url=image_url,
        image_url_outer=image_url,
        title=title,
        images=images,
    )


async def parse_sku_from_dom_content(
    content: str, *, product_id: str, sku_id: str, source: str, product_url: str
) -> dict:
    """
    解析页面内容
    """
    tree = etree.HTML(content)

    # 获取商品名称
    product_name_node = tree.xpath('//*[@id="buy-box"]/div/h1/text()')
    product_name = product_name_node[0] if product_name_node else None
    log.info(f"{product_name=}")

    # 获取价格
    price_node = tree.xpath('//*[@id="buy-box"]/div/div/div[1]/div[1]/span/text()')
    price = price_node[0] if price_node else None

    log.info(f"{price=}")
    # 原价抓取存在问题, 可能是价格区间
    # original_price = tree.xpath("//*[@id='buy-box']/div/div/div[1]/div[1]/div/span/text()")[0]
    # log.info(original_price)

    # 获取颜色
    color_node = tree.xpath('//*[@id="swatch-label--Color"]/span[2]/text()')
    color = color_node[0] if color_node else None
    log.info(f"{color=}")
    # fit_size 适合人群
    attributes = []
    fit_and_size = tree.xpath(
        "//*[@id='buy-box-wrapper-id']/div/div[2]/div/div/div/div[2]/div[1]/div/div[1]/div/div/ul/li/text()"
    )
    log.info(fit_and_size)
    attributes.extend(fit_and_size)
    # 产品详情
    product_details: list = tree.xpath(
        '//*[@id="buy-box-wrapper-id"]/div/div[2]/div/div/div/div[2]/div[2]/div/div[1]/div/ul/li/span/text()'
    )
    attributes.extend(product_details)
    log.info(product_details)
    # 面料
    fabric_and_care: list = tree.xpath(
        "//*[@id='buy-box-wrapper-id']/div/div[2]/div/div/div/div[2]/div[3]/div/div[1]/div/ul/li/span/text()"
    )
    attributes.extend(fabric_and_care)
    log.info(fabric_and_care)
    # TODO  下载 模特图片

    model_image_urls_raw = tree.xpath("//*[@id='product']/div[1]/div[1]/div[3]/div[2]/div/div/div/a/@href")
    model_image_urls = []
    for item in model_image_urls_raw:
        log.info(item)
        model_image_urls.append("https://www.gap.com" + item)
    # product_id = product_details[-1] if product_details else None
    if len(model_image_urls) > 0:
        model_image_url = model_image_urls[0]
        image_url = model_image_urls[-1]
    else:
        model_image_url = None
        image_url = None

    pdp_info = dict(
        price=price,
        # original_price=original_price,
        product_name=product_name,
        color=color,
        fit_size=fit_and_size,
        product_details=product_details,
        fabric_and_care=fabric_and_care,
        product_id=product_id,
        sku_id=sku_id,
        sku_url=product_url,
        source=source,
        model_image_url=model_image_url,
        image_url=image_url,
        image_url_outer=image_url,
        model_image_urls=model_image_urls,
        attributes=attributes,
    )
    # 将从页面提取到的信息保存的数据库
    save_sku_data(pdp_info)

    save_product_data(
        dict(
            product_id=product_id,
            attributes=attributes,
            product_url=product_url,
            source=source,
            color=color,
            fit_size=fit_and_size,
            product_details=product_details,
            fabric_and_care=fabric_and_care,
        )
    )
    return pdp_info


async def get_reviews_from_url_by_id(product_id: str):
    async with httpx.AsyncClient(timeout=settings.httpx_timeout) as client:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Referer": "https://www.gap.com",
        }
        url = f"https://display.powerreviews.com/m/1443032450/l/en_US/product/{product_id}/reviews?_noconfig=true"
        response = await client.get(url=url, headers=headers)
        log.info(response.text)
        return response.json()


async def scroll_to_bottom_v1(page: Page):
    # 获取页面的高度
    previous_height = await page.evaluate("document.body.scrollHeight")
    while True:
        # 滚动到页面底部
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        # 等待页面加载新内容
        await page.wait_for_timeout(random.randrange(2000, 4000, 500))  # 等待 4~8 秒
        # 获取新的页面高度
        new_height = await page.evaluate("document.body.scrollHeight")
        if new_height == previous_height:
            break
        previous_height = new_height


async def scroll_to_bottom(page: Page, scroll_pause_time: int = 1000, max_scroll_attempts: int = 20):
    """
    滚动页面到底部，以加载所有动态内容。

    :param page: Playwright页面对象
    :param scroll_pause_time: 每次滚动后等待的时间（毫秒）
    :param max_scroll_attempts: 最大滚动次数
    """
    previous_height = await page.evaluate("document.body.scrollHeight")
    scroll_attempts = 0

    while scroll_attempts < max_scroll_attempts:
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(scroll_pause_time)

        new_height = await page.evaluate("document.body.scrollHeight")
        if new_height == previous_height:
            break
        previous_height = new_height
        scroll_attempts += 1

    if scroll_attempts >= max_scroll_attempts:
        log.info("Reached maximum scroll attempts")
    else:
        log.info(f"Scrolled to bottom after {scroll_attempts} attempts")


async def scroll_page(page: Page, scroll_pause_time: int = 1000):
    viewport_height = await page.evaluate("window.innerHeight")
    i = 0
    current_scroll_position = 0
    while True:
        # 滚动视口高度
        i += 1
        # log.info(f"第{i}次滚动, 滚动高度: {viewport_height}")
        current_scroll_position += viewport_height
        # log.info(f"当前滚动位置: {current_scroll_position}")
        # 滚动到新的位置
        await page.evaluate(f"window.scrollTo(0, {current_scroll_position})")
        # 滚动到页面底部
        # await page.evaluate(f"window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(scroll_pause_time / 1000)
        # await page.wait_for_timeout(scroll_pause_time)
        await page.wait_for_load_state("domcontentloaded")
        # 重新获取页面高度
        scroll_height = await page.evaluate("document.body.scrollHeight")
        # 获取当前视口位置
        current_viewport_position = await page.evaluate("window.scrollY + window.innerHeight")
        # log.info(f"页面高度: {scroll_height}")
        # log.info(f"当前视口位置: {current_viewport_position}")

        if current_viewport_position >= scroll_height or current_scroll_position >= scroll_height:
            # log.info("滚动到底部")
            break
        # previous_height = new_height


async def parse_category_from_api(
    data: dict, page: Page, gender: str, *, source: str, primary_category: str, sub_category: str
):
    """
    解析类型页面的API接口
    """
    results = []
    products: list = data.get("products", [])
    product_count = int(data.get("totalColors", 0))
    category_skus = data.get("categories")[0]["ccList"]
    skus_index = [(item["styleId"], item["ccId"]) for item in category_skus]
    pagination = dict(
        current_page=data.get("pagination").get("currentPage") if data.get("pagination") else None,
        page_size=data.get("pagination").get("currentPage") if data.get("pagination") else None,
        total_pages=data.get("pagination").get("currentPage") if data.get("pagination") else None,
        total=data.get("totalColors"),
    )
    log.info(f"通过接口, 共发现{product_count}件商品")
    for product in products:
        # TODO 需要商品图片连接
        result = dict(
            product_id=product.get("styleId", None),  # 商品id
            product_name=product.get("styleName", None),  # 商品名称
            rating=product.get("reviewScore", None),  # 评分
            review_count=product.get("reviewCount", None),  # 评论数量
            rating_count=product.get("reviewCount", None),  # 评分数量
            type=product.get("webProductType", None),  # 商品类型
            category=product.get("webProductType", None),  # 商品类别
            released_at=product.get("releaseDate", None),  # 发布日期
            brand="gap",  # 品牌
            gender=gender,  # 性别
            source=source,  # 数据来源
        )

        skus = product.get("styleColors", [])
        # 将sku_id添加到product中
        if len(skus) > 0:
            result["sku_id"] = skus[0].get("ccId", None)
            images = skus[0].get("images", [])
            # for item in images:
            #     # 获取主图
            #     if item["type"] == "AV6_Z":
            #         result["image_url"] = "https://www.gap.com" + item.get("path") if item.get("path") else None
            #         continue
            #     if item["type"] == "Z":
            #         result["model_image_url"] = "https://www.gap.com" + item.get("path") if item.get("path") else None
            #     if item["type"] == "AV1_Z":
            #         result["_image_url"] = "https://www.gap.com" + item.get("path") if item.get("path") else None

            # 将图片上传到oss
            # 下载图片
            # FIXME
            # try:
            #     async with httpx.AsyncClient(timeout=15) as client:
            #         response = await client.get(result["image_url"] + "?q=h&w=322")
            #         image_bytes = response.content
            #         image_url_stored = upload_image(
            #             filename=result["image_url"].replace("https://www.gap.com/", ""),
            #             data=image_bytes,
            #             prefix=f"crawlers/{PROVIDER}",
            #         )
            #
            #         result["image_url_stored"] = image_url_stored
            # except Exception as exc:
            #     log.error(f"下载图片失败: {exc}")

        sub_results = []
        product_dir = settings.data_dir.joinpath(source, primary_category, sub_category, str(result["product_id"]))
        product_dir.mkdir(parents=True, exist_ok=True)
        for sku in skus:
            sub_result = dict(
                sku_id=sku.get("ccId", None),  # sku id
                product_id=product.get("styleId", None),  # 商品id
                product_name=product.get("styleName", None),  # 商品名称
                sku_name=sku.get("ccName", None),  # sku 名称
                color=sku.get("ccName", None),  # 颜色
                description=sku.get("ccShortDescription", None),  # sku 描述
                inventory=sku.get("inventoryCount", None),  # 库存
                size=None,
                inventory_status=sku.get("inventoryStatus", None),  # 库存状态
                vendor=sku.get("vendorName", None),  # 供应商
                source=source,
            )
            sub_results.append(sub_result)
            sku_dir = product_dir.joinpath(str(sub_result["sku_id"]))
            sku_dir.mkdir(parents=True, exist_ok=True)
            with open(f"{sku_dir}/sku.json", "w") as f:
                f.write(json.dumps(sub_result, indent=4, ensure_ascii=False))
        result["skus"] = sub_results
        # 保存SKU数据
        save_sku_data(sub_results)
        with open(
            f"{settings.data_dir.joinpath(source, primary_category, sub_category, str(result['product_id']))}/product.json",
            "w",
        ) as f:
            f.write(json.dumps(result, indent=4, ensure_ascii=False))
        results.append(result)
    # 保存商品数据
    save_product_data(results)

    return results, product_count, pagination, skus_index
    pass


def parse_reviews_from_api(r: dict) -> tuple[list[dict], int | None]:
    # 获取分页信息
    review_domain = "https://display.powerreviews.com"
    paging_raw = r.get("paging", {})
    total_count = paging_raw.get("total_results", None) if paging_raw else None
    current_page = paging_raw.get("current_page_number", None) if paging_raw else None
    total_results = paging_raw.get("total_results", None) if paging_raw else None
    total_pages = paging_raw.get("pages_total", None) if paging_raw else None

    # 获取评论
    reviews: list = r.get("results", [])[0].get("reviews", [])

    my_reviews = []

    for review in reviews:
        my_review = dict(
            review_id=review.get("review_id", None),
            proudct_name=review.get("details").get("product_name", None) if review.get("details") else None,
            title=review.get("details").get("headline", None) if review.get("details") else None,
            comment=review.get("details").get("comments", None) if review.get("details") else None,
            nickname=review.get("details").get("nickname", None) if review.get("details") else None,
            product_id=review.get("details").get("product_page_id", None) if review.get("details") else None,
            sku_id=review.get("details").get("product_variant", None) if review.get("details") else None,
            helpful_votes=review.get("metrics").get("helpful_votes", None) if review.get("metrics") else None,
            not_helpful_votes=review.get("metrics").get("not_helpful_votes", None) if review.get("metrics") else None,
            rating=review.get("metrics").get("rating", None) if review.get("metrics") else None,
            helpful_score=review.get("metrics").get("helpful_score", None) if review.get("metrics") else None,
            source=source,
        )
        my_reviews.append(my_review)
    return my_reviews, total_count


def get_cookies_from_playwright(cookies: dict) -> str:
    cookies_dict = {cookie["name"]: cookie["value"] for cookie in cookies}
    return "; ".join([f"{key}={value}" for key, value in cookies_dict.items()])


async def fetch_reviews(
    semaphore,
    url,
    headers,
    product_id: str | None = None,
    index: int | None = None,
    *,
    primary_category: str,
    sub_category: str,
):
    async with semaphore:
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()  # 检查HTTP请求是否成功
                json_dict = response.json()
                raw_review_data = settings.data_dir.joinpath(
                    source, primary_category, sub_category, product_id, "raw_data"
                )
                raw_review_data.mkdir(parents=True, exist_ok=True)
                with open(f"{raw_review_data}/review-{product_id}-{index:02d}.json", "w") as f:
                    f.write(json.dumps(json_dict, indent=4, ensure_ascii=False))
                return parse_reviews_from_api(json_dict)[0]
        except Exception as exc:
            log.error(f"获取评论失败, {exc}")


async def fetch_images(semaphore: asyncio.Semaphore, url, headers, file_path: Path | str):
    async with semaphore:
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                log.debug(f"下载图片: {url}")
                response = await client.get(url, headers=headers)
                response.raise_for_status()  # 检查HTTP请求是否成功
                image_bytes = response.content
                with open(f"{str(file_path)}", "wb") as f:
                    f.write(image_bytes)
        except Exception as exc:
            log.error(f"下载图片失败, {exc}")


async def go_to_pdp_page(semapage: Page, pdp_url: str):
    # TODO  并发获取商品
    pass


# 这个函数是脚本的主入口点。
# 它创建一个playwright对象，并将其传递给run函数。
async def main():
    # 创建一个playwright对象并将其传递给run函数
    async with async_playwright() as p:
        # TODO 指定要下载的类别连接
        # base_url: str = "https://www.gap.com/browse/category.do?cid=14417#pageId=0&department=48"
        # base_url: str = "https://www.gap.com/browse/category.do?cid=1127938&department=136#department=136&pageId=0"
        # for base_url in urls:
        # log.info(f"开始抓取: {base_url}")
        # tasks = [run(p, url) for url in urls]
        # await asyncio.gather(*tasks)
        await run(p, urls)
        ...


# 这是脚本的入口点。
# 它开始执行main函数。
if __name__ == "__main__":
    # 指定本地代理
    # os.environ["http_proxy"] = "http://127.0.0.1:23457"
    # os.environ["https_proxy"] = "http://127.0.0.1:23457"
    # os.environ["all_proxy"] = "socks5://127.0.0.1:23457"
    asyncio.run(main())
