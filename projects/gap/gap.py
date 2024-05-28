import asyncio
import json
import logging
import random
import re
from enum import Enum
from pathlib import Path

import httpx
from lxml import etree
from playwright.async_api import async_playwright, Playwright, Page, Route
from sqlalchemy import insert
from sqlalchemy import select
from sqlalchemy.orm import Session

from crawler.config import settings
from crawler.db import engine
from crawler.models import ProductReview, ProductSKU, Product, Base

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
urls = [
    "https://www.gap.com/browse/category.do?cid=1127938&department=136#department=136&pageId=0",
    "https://www.gap.com/browse/category.do?cid=1127938&department=136#department=136&pageId=1",
    "https://www.gap.com/browse/category.do?cid=1127938&department=136#department=136&pageId=2",
    "https://www.gap.com/browse/category.do?cid=1127938&department=136#department=136&pageId=3",
    "https://www.gap.com/browse/category.do?cid=1127938&department=136#department=136&pageId=4",
    "https://www.gap.com/browse/category.do?cid=1127938&department=136#department=136&pageId=5",
    "https://www.gap.com/browse/category.do?cid=1127938&department=136#department=136&pageId=6",
    "https://www.gap.com/browse/category.do?cid=1127938&department=136#department=136&pageId=7",
    "https://www.gap.com/browse/category.do?cid=1127938&department=136#department=136&pageId=8",
]
playwright_timeout = settings.playwright.timeout or 1000 * 60 * 5

PROVIDER = "gap"

__doc__ = """
    金茂爬虫, 主要通过按类别爬取和按搜索爬取两种方式
"""


class Category(Enum):
    girls = 14417


# 这个函数负责启动一个浏览器，打开一个新页面，并在页面上执行操作。
# 它接受一个Playwright对象作为参数。


def get_product_id(url: str) -> str:
    parsed_url = httpx.URL(url)
    return parsed_url.params.get("pid")[:-3]


async def run(playwright: Playwright, base_url: str) -> None:
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
            headless=True,
            # headless=False,
            # devtools=True,
        )
    else:
        browser = await chromium.launch(headless=True, devtools=True)
        context = await browser.new_context()

    # 设置全局超时
    context.set_default_timeout(settings.playwright.timeout)
    # 创建一个新的浏览器上下文，设置视口大小
    # context = await browser.new_context(viewport={"width": 1920, "height": 1080})
    # 在浏览器上下文中打开一个新页面

    pages = context.pages

    if pages:
        page = pages[0]
    else:
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

        async def handle_main_route(route: Route):
            """拦截api"""
            request = route.request
            print(request.url)
            # api 连接可优化
            if ("cc" and "products" in request.url) and request.resource_type in ("xhr", "fetch"):
                print("获取 headers和Cookie")
                print(request.headers)
                # 获取cookie
                cookies = await context.cookies(request.url)
                cookie_str = "; ".join([f"{cookie['name']}={cookie['value']}" for cookie in cookies])

                response = await route.fetch()
                print(response.url)
                # print(f"接口原始数据: {await response.text()}")
                json_dict = await response.json()
                # print(f"类别接口数据: \n{json_dict}")
                # TODO  获取products by categories

                products, _product_count, _pages, _sku_index = parse_categories(json_dict)
                nonlocal product_count
                product_count = _product_count
                nonlocal pages
                pages = _pages
                nonlocal sku_index
                sku_index = _sku_index

                products_list.extend(products)

                print(f"序列化后数据: {products}")
            await route.continue_()

        # 拦截 API
        await page.route("**/api.gap.com/**", handle_main_route)

        # TODO 指定url
        # 导航到指定的URL
        await page.goto(base_url, timeout=playwright_timeout)
        # 其他操作...
        # 暂停执行
        # await page.pause()
        await page.wait_for_timeout(3000)
        await page.wait_for_load_state("load")  # 等待页面加载

        scroll_pause_time = random.randrange(1000, 2500, 500)
        # await page.wait_for_timeout(1000)
        await scroll_page(page, scroll_pause_time=scroll_pause_time)
        # await page.pause()
        await page.wait_for_load_state("load")  # 等待页面加载完成
        print(f"页面加载完成后页面高度{await page.evaluate('document.body.scrollHeight')}")

        if "category.do" in base_url:
            page_type = "category"
            total_class_name = "category-page-k52n89"
        elif "search.do" in base_url:
            page_type = "search"
            total_class_name = "css-k52n89"
        else:
            page_type = "other"
            total_class_name = "css-3e6p0j"
        # selector = f".{total_class_name}"
        # await page.wait_for_selector(selector, timeout=10000)
        # element = await page.query_selector(selector)
        element = page.get_by_label("items in the product grid")

        if not element:
            print("未获取到选择器")
            await page.pause()
        text = await element.first.text_content()
        items: int = int(re.match(r"(\d+)", text).group(1)) if text else 0
        print(f"共发现{items}件商品")
        # await page.pause()
        # 提取所有商品链接
        # TODO 改为获取所有url
        main_content = await page.content()
        main_tree = etree.HTML(main_content)
        # print("从route获取到的数据: ", result)
        print(f"拦截路由更新: {products_list}")
        print(f"拦截路由更新: {product_count}")
        print(f"拦截路由更新: {pages}")
        print(f"拦截路由更新: 数量{len(sku_index)},  {sku_index}")
        pdp_urls = main_tree.xpath("//*[@id='faceted-grid']/section/div/div/div/div[1]/a/@href")
        print(f"获取到{len(pdp_urls)}个商品链接")

        for product_id, sku_id in sku_index:
            # new_page = await context.new_page()
            # search-page > div > div > div > div.search-page__product-grid.css-1xlfwl6 > section > div
            # if page_type == "category":
            #     locator = page.locator(f"#faceted-grid > section > div > div:nth-child({item}) a")
            #     pdp_url = await locator.first.get_attribute("href")
            #
            # elif page_type == "search":
            #     locator = page.locator(
            #         f"#search-page > div > div > div > div.search-page__product-grid.css-1xlfwl6 > section > div > div:nth-child({item}) > div > a "
            #     )
            #     pdp_url = await locator.first.get_attribute("href")
            #
            # else:
            #     pdp_url = ""
            #     locator = None
            # print(f" 页面类型: {page_type}, 第{item}个, pdp_url: {pdp_url}")
            # if not locator:
            #     print("error, 未获取到url")
            #     return
            # 进入新页面url
            # time.sleep(1)
            # continue

            # product_detail_page 产品详情页
            pdp_url = f"https://www.gap.com/browse/product.do?pid={sku_id}#pdp-page-content"

            sku_id = int(httpx.URL(pdp_url).params.get("pid", 0))
            print(sku_id)
            sub_page = await context.new_page()

            async with sub_page:
                # await sub_page.goto(pdp_url)
                await sub_page.route(
                    "**/*",
                    lambda route: route.abort() if route.request.resource_type == "image" else route.continue_(),
                )

                async def handle_route(route: Route):
                    request = route.request

                    if "/reviews" in request.url:
                        response = await route.fetch()
                        json_dict = await response.json()
                        # TODO  获取评论信息
                        reviews, total_count = parse_reviews_from_api(json_dict)
                        print(f"预期评论数{total_count}, reviews: {reviews}, {len(reviews)}")
                        page_size = 25
                        total_pages = (total_count + page_size - 1) // page_size
                        print(f"总页数{total_pages}")

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
                            tasks.append(fetch_reviews(semaphore, review_url, request.headers))

                        new_reviews = await asyncio.gather(*tasks)
                        for review in new_reviews:
                            reviews.extend(review)

                        print(f"实际评论数{len(reviews)}")
                        # 存储评论信息
                        product_store_dir = settings.data_dir.joinpath(PROVIDER, product_id)
                        product_store_dir.mkdir(parents=True, exist_ok=True)
                        with open(f"{product_store_dir}/review-{product_id}.json", "w") as f:
                            print(f"存储评论到文件{product_store_dir}/review.json")
                            f.write(json.dumps(reviews))

                        product_store_dir2 = settings.data_dir.joinpath(PROVIDER, "reviews")
                        product_store_dir2.mkdir(parents=True, exist_ok=True)
                        with open(f"{product_store_dir2}/review-{product_id}.json", "w") as f:
                            print(f"存储评论到文件{product_store_dir}/review-{product_id}.json")
                            f.write(json.dumps(reviews))

                        # print("获取评论信息")
                        # with open(f"{settings.project_dir.joinpath('data', 'product_info')}/data-.json", "w") as f:
                        #     f.write(json.dumps(json_dict))
                        # pass
                    # if "api" in request.pdp_url or "service" in request.pdp_url:
                    #
                    #     print(f"API Request URL: {request.pdp_url}")
                    await route.continue_()

                await sub_page.route("**/display.powerreviews.com/**", handle_route)

                # await sub_page.route(
                #     "**/*",
                #     lambda route: route.abort() if "api.gap.com" and "look" in route.request.url else route.continue_(),
                # )
                async def handle_route2(route: Route):
                    request = route.request
                    print(request.url)
                    if "api.gap.com" and "complete-the-look" in request.url:
                        response = await route.fetch()
                        json_dict = await response.json()
                        result = await parse_sku_from_api(
                            sku=json_dict,
                            sku_id=sku_id,
                        )
                        # 将详情数据填充到sku_detail
                        sku_detail["from_api"] = result
                        # store file to disk

                        # # create dir if not exists
                        # prod_path = settings.project_dir.joinpath("data", PROVIDER, "product_info")
                        #
                        # if not settings.project_dir.joinpath("data", PROVIDER, "product_info").exists():
                        #     os.makedirs(settings.project_dir.joinpath("data", PROVIDER, "product_info"))
                        #
                        # with open(
                        #     f"{settings.project_dir.joinpath('data', PROVIDER, 'product_info')}/data-{sku_id}.json",
                        #     "w",
                        # ) as f:
                        #     f.write(json.dumps(json_dict))
                        # print("")

                        # 将数据存储到数据库中
                        # with Session(engine) as session:
                        #     stmt = insert(models.Product).values(result)
                        #     session.a
                    # 获取数据对象
                    # if "complete-the-look" in request.pdp_url:
                    #     response = await route.fetch()
                    #     json_dict = await response.json()
                    #     # 将数据存储到文件中
                    #     with open(
                    #         f"{settings.project_dir.joinpath('data', 'product_info')}/data-{sku_id}.json", "w"
                    #     ) as f:
                    #         f.write(json.dumps(json_dict))
                    await route.continue_()

                # 进入新页面
                await sub_page.goto(pdp_url, timeout=playwright_timeout)
                # sub_page.on("request", lambda request: print(f"Request: {request.pdp_url}"))
                # sub_page.on("response", lambda response: print(f"Request: {response.pdp_url}"))

                # 拦截所有api pdp_url
                await sub_page.wait_for_timeout(5 * 1000)
                scroll_pause_time = random.randrange(1500, 2500, 500)
                # await page.wait_for_timeout(1000)
                await scroll_page(sub_page, scroll_pause_time=scroll_pause_time)
                # await page.wait_for_load_state("load")
                content = await sub_page.content()
                # 获取产品详情页(pdp)信息
                dom_pdp_info = await parse_sku_from_dom_content(content)
                # TODO 更新信息到数据库和json文件 或者等从接口拿取后统一写入
                model_image_urls = dom_pdp_info.get("model_image_urls", [])
                base_url = "https://www.gap.com"
                image_tasks = []
                semaphore = asyncio.Semaphore(10)  # 设置并发请求数限制为10
                sku_dir = settings.data_dir.joinpath(PROVIDER, str(product_id), str(sku_id))
                sku_model_dir = sku_dir.joinpath("model")
                sku_model_dir.mkdir(parents=True, exist_ok=True)
                for index, url in enumerate(model_image_urls):
                    image_tasks.append(
                        fetch_images(
                            semaphore,
                            base_url + url,
                            {},
                            file_path=sku_model_dir.joinpath(f"model-{index+1}-{url.split('/')[-1]}"),
                        )
                    )

                await asyncio.gather(*image_tasks)

                # await page.pause()
                sku_detail = {
                    "from_api": None,
                    "from_dom": dom_pdp_info,
                }

                # 关闭登录框
                # TODO 关闭弹窗
                # await sub_page.get_by_label("close email sign up modal").click()
                print(f"进入商品页面: {pdp_url}")
                await sub_page.wait_for_load_state("domcontentloaded")
                # await sub_page.wait_for_timeout(60000)
                # await sub_page.wait_for_selector("h1")

                # 商品标题
                product_title = await sub_page.locator("#buy-box > div > h1").text_content()
                # 商品id, pid
                print(f"商品: {sku_id}, 标题: {product_title}")
                # 获取评论

                # await sub_page.pause()

                # async with page.expect_popup() as sub_page:

                # await new_page.goto()
                # async with page.expect_popup() as sub_page:
                #     "#\37 36395012 > a"
                #     "#\37 36395012 > a"
                # goods = page.locator(
                #     f"#product > div.l--sticky-wrapper.pdp-mfe-wjfrns > div.l--breadcrumb-photo-wrapper.pdp-mfe-89s1nj > div.product_photos-container > div.brick-and-carousel-wrapper.pdp-mfe-m9u4rn > div > div:nth-child({item}) > div > a"
                # )
                # print()
                # await page.pause()
                await asyncio.sleep(random.randrange(5, 12, 3))

            # break
    # 关闭浏览器context
    await context.close()


async def browse_by_category():
    """按类别(category)爬取"""
    pass


async def browse_by_division():
    """按部门(division)浏览"""
    pass


async def browse_by_search():
    """按搜索(search)浏览"""


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
        title=title,
        images=images,
    )
    # api_url = "https://lit.findmine.com/api/v3/complete-the-look"
    # query_parameters = f"?application=6DEEFB0257EA51840E0A&language=en&product_color_id=00&product_id={product_id}&product_in_stock=true&product_on_sale=true&product_price=58&region=us&return_pdp_item=true&fm_session_id=dbd2b6af-f4fb-4a05-88ac-ae2355c74296"
    # async with httpx.AsyncClient(timeout=settings.httpx_timeout) as client:
    #     url = api_url + query_parameters
    #     response = await client.get(url)


async def get_products_old(products: dict) -> list[dict]:
    """从接口获取产品信息"""
    pass
    results = []
    products: list = products["products"]
    for product in products:
        result = dict(
            id=int(product["styleId"]),  # 商品id
            title=product["styleName"],  # 商品标题
            review_score=product["reviewScore"],  # 评分
            review_count=product["reviewCount"],  # 评论数量
            type=product["webProductType"],  # 商品类型
        )
        skus = product["styleColors"]
        sub_results = []
        for sku in skus:
            sub_result = dict(
                id=sku["ccId"],  # sku id
                product_id=product["styleId"],  # 商品id
                name=sku["ccName"],  # sku 名称
                description=sku["ccShortDescription"],  # sku 描述
                inventory=sku["inventoryCount"],  # 库存
                inventory_status=sku["inventoryStatus"],  # 库存状态
                vendor=sku["vendorName"],  # 供应商
            )
            sub_results.append(sub_result)
            ...
        result["skus"] = sub_results
        results.append(result)
    return results


async def parse_sku_from_dom_content(content: str):
    """
    解析页面内容
    """
    tree = etree.HTML(content)

    # 获取商品名称
    proudct_name = tree.xpath('//*[@id="buy-box"]/div/h1/text()')[0]
    proudct_name = proudct_name.replace("|", "")
    proudct_name = proudct_name.replace('"', "")
    print(proudct_name)
    # 获取价格
    price = tree.xpath('//*[@id="buy-box"]/div/div/div[1]/div[1]/span/text()')[0]
    # original_price = tree.xpath("//*[@id='buy-box']/div/div/div[1]/div[1]/div/span/text()")[0]
    print(price)
    # print(original_price)

    # 获取颜色
    color = tree.xpath('//*[@id="swatch-label--Color"]/span[2]/text()')[0]
    print(color)
    product_name = tree.xpath("//*[@id='buy-box']/div/h1/text()")[0]
    # fit_size 适合人群
    fit_and_size = tree.xpath(
        "//*[@id='buy-box-wrapper-id']/div/div[2]/div/div/div/div[2]/div[1]/div/div[1]/div/div/ul/li/text()"
    )
    print(fit_and_size)
    # 产品详情
    product_details: list = tree.xpath(
        '//*[@id="buy-box-wrapper-id"]/div/div[2]/div/div/div/div[2]/div[2]/div/div[1]/div/ul/li/span/text()'
    )
    print(product_details)
    # 面料
    fabric_and_care: list = tree.xpath(
        "//*[@id='buy-box-wrapper-id']/div/div[2]/div/div/div/div[2]/div[3]/div/div[1]/div/ul/li/span/text()"
    )
    print(fabric_and_care)
    # TODO  下载 模特图片

    model_image_urls = tree.xpath("//*[@id='product']/div[1]/div[1]/div[3]/div[2]/div/div/div/a/@href")
    product_id = product_details[-1]
    return dict(
        price=price,
        # original_price=original_price,
        product_name=product_name,
        color=color,
        fit_size=fit_and_size,
        product_details=product_details,
        fabric_and_care=fabric_and_care,
        product_id=product_id,
        model_image_urls=model_image_urls,
    )


async def get_reviews_from_url_by_id(product_id: str):
    async with httpx.AsyncClient(timeout=settings.httpx_timeout) as client:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Referer": "https://www.gap.com",
        }
        url = f"https://display.powerreviews.com/m/1443032450/l/en_US/product/{product_id}/reviews?_noconfig=true"
        response = await client.get(url=url, headers=headers)
        print(response.text)
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
        print("Reached maximum scroll attempts")
    else:
        print(f"Scrolled to bottom after {scroll_attempts} attempts")


async def scroll_page(page: Page, scroll_pause_time: int = 1000):
    viewport_height = await page.evaluate("window.innerHeight")
    i = 0
    current_scroll_position = 0
    while True:
        # 滚动视口高度
        i += 1
        print(f"第{i}次滚动, 滚动高度: {viewport_height}")
        current_scroll_position += viewport_height
        print(f"当前滚动位置: {current_scroll_position}")
        # 滚动到新的位置
        await page.evaluate(f"window.scrollTo(0, {current_scroll_position})")
        # 滚动到页面底部
        # await page.evaluate(f"window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(scroll_pause_time / 1000)
        # await page.wait_for_timeout(scroll_pause_time)
        await page.wait_for_load_state("load")
        # 重新获取页面高度
        scroll_height = await page.evaluate("document.body.scrollHeight")
        # 获取当前视口位置
        current_viewport_position = await page.evaluate("window.scrollY + window.innerHeight")
        print(f"页面高度: {scroll_height}")
        print(f"当前视口位置: {current_viewport_position}")

        if current_viewport_position >= scroll_height or current_scroll_position >= scroll_height:
            print("滚动到底部")
            break
        # previous_height = new_height


def parse_categories(
    data: dict,
):
    """
    解析类型页面的API接口
    """
    results = []
    products_list: list = data.get("products", [])
    product_count = int(data.get("totalColors", 0))
    category_skus = data.get("categories")[0]["ccList"]
    skus_index = [(item["styleId"], item["ccId"]) for item in category_skus]
    pagination = dict(
        current_page=data.get("pagination").get("currentPage") if data.get("pagination") else None,
        page_size=data.get("pagination").get("currentPage") if data.get("pagination") else None,
        total_pages=data.get("pagination").get("currentPage") if data.get("pagination") else None,
        total=data.get("totalColors"),
    )
    print(f"通过接口, 共发现{product_count}件商品")
    for product in products_list:
        result = dict(
            id=product.get("styleId", None),  # 商品id
            title=product.get("styleName", None),  # 商品标题
            review_score=product.get("reviewScore", None),  # 评分
            review_count=product.get("reviewCount", None),  # 评论数量
            type=product.get("webProductType", None),  # 商品类型
        )

        skus = product.get("styleColors", [])
        sub_results = []
        product_dir = settings.data_dir.joinpath(PROVIDER, str(result["id"]))
        product_dir.mkdir(parents=True, exist_ok=True)
        for sku in skus:
            sub_result = dict(
                id=sku.get("ccId", None),  # sku id
                product_id=product.get("styleId", None),  # 商品id
                name=sku.get("ccName", None),  # sku 名称
                description=sku.get("ccShortDescription", None),  # sku 描述
                inventory=sku.get("inventoryCount", None),  # 库存
                inventory_status=sku.get("inventoryStatus", None),  # 库存状态
                vendor=sku.get("vendorName", None),  # 供应商
            )
            sub_results.append(sub_result)
            sku_dir = product_dir.joinpath(str(sub_result["id"]))
            sku_dir.mkdir(parents=True, exist_ok=True)
            with open(f"{sku_dir}/sku.json", "w") as f:
                f.write(json.dumps(sub_result))
        result["skus"] = sub_results
        with open(f"{settings.data_dir.joinpath(PROVIDER, str(result['id']))}/product.json", "w") as f:
            f.write(json.dumps(result))
        results.append(result)

    return (results, product_count, pagination, skus_index)
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
        )
        my_reviews.append(my_review)
    return my_reviews, total_count


def get_cookies_from_playwright(cookies: dict) -> str:
    cookies_dict = {cookie["name"]: cookie["value"] for cookie in cookies}
    return "; ".join([f"{key}={value}" for key, value in cookies_dict.items()])


def save_review_data(data: dict):
    """
    保存数据为json 和数据库
    """
    data = field_filter(ProductReview, data)
    with Session(engine) as session:
        review = session.execute(select(ProductReview).filter(ProductReview.product_id == id)).scalars().one_or_none()
        if review:
            for key, value in data.items():
                setattr(review, key, value)
            session.add(review)
            session.commit()
            session.refresh(review)
        else:
            stmt = insert(ProductReview).values(data)
            session.execute(stmt)
            session.commit()


def save_sku_data(data: dict | list[dict]):
    """
    保存数据为json 和数据库
    """
    if isinstance(data, dict):
        id = data["id"]
        data = field_filter(ProductSKU, data)

        with Session(engine) as session:
            sku = session.execute(select(ProductSKU).filter(ProductSKU.id == id)).scalars().one_or_none()
            if sku:
                for key, value in data.items():
                    setattr(sku, key, value)
                session.add(sku)
                session.commit()
                session.refresh(sku)
            else:
                stmt = insert(ProductSKU).values(data)
                session.execute(stmt)
                session.commit()
    elif isinstance(data, list):
        with Session(engine) as session:
            for sku_data in data:
                id = sku_data["id"]
                sku = session.execute(select(ProductSKU).filter(ProductSKU.id == id)).scalars().one_or_none()
                if sku:
                    for key, value in sku_data.items():
                        setattr(sku, key, value)
                    session.add(sku)
                    session.commit()
                    session.refresh(sku)
                else:
                    stmt = insert(ProductSKU).values(sku_data)
                    session.execute(stmt)
                    session.commit()


def save_product_data(data: dict):
    """
    保存数据为json 和数据库
    """
    id = data["id"]
    data = field_filter(Product, data)
    with Session(engine) as session:
        product = session.execute(select(Product).filter(Product.id == id)).scalars().one_or_none()
        if product:
            for key, value in data.items():
                setattr(product, key, value)
            session.add(product)
            session.commit()
            session.refresh(product)
        else:
            logging.info(f"insert product data: {data}")
            stmt = insert(ProductSKU).values(data)
            session.execute(stmt)
            session.commit()


def field_filter(model: Base, data: dict) -> dict:
    """
    过滤字段
    """
    return {key: value for key, value in data.items() if key in model.__table__.columns}


async def fetch_reviews(semaphore, url, headers):
    async with semaphore:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()  # 检查HTTP请求是否成功
            json_dict = response.json()
            return parse_reviews_from_api(json_dict)[0]


async def fetch_images(semaphore: asyncio.Semaphore, url, headers, file_path: Path | str):
    async with semaphore:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()  # 检查HTTP请求是否成功
            image_bytes = response.content
            with open(f"{str(file_path)}", "wb") as f:
                f.write(image_bytes)


async def go_to_pdp_page(semapage: Page, pdp_url: str):
    # TODO  并发获取商品
    pass


# 这个函数是脚本的主入口点。
# 它创建一个playwright对象，并将其传递给run函数。
async def main():
    # 创建一个playwright对象并将其传递给run函数
    async with async_playwright() as p:
        # TODO 指定要下载的类别连接
        base_url: str = "https://www.gap.com/browse/category.do?cid=14417#pageId=0&department=48"
        base_url: str = "https://www.gap.com/browse/category.do?cid=1127938&department=136#department=136&pageId=0"
        # for base_url in urls:
        await run(p, base_url)
        ...


# 这是脚本的入口点。
# 它开始执行main函数。
if __name__ == "__main__":
    # 指定本地代理
    # os.environ["http_proxy"] = "http://127.0.0.1:23457"
    # os.environ["https_proxy"] = "http://127.0.0.1:23457"
    # os.environ["all_proxy"] = "socks5://127.0.0.1:23457"
    asyncio.run(main(), debug=True)
