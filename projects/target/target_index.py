import asyncio
import logging
import random
import re
from datetime import datetime
from mimetypes import guess_extension
from pathlib import Path

import httpx
import redis.asyncio as redis
from fake_useragent import UserAgent
from playwright.async_api import Playwright, async_playwright, BrowserContext, Route, Page

from crawler.config import settings
from crawler.store import save_product_data, save_review_data
from crawler.utils import scroll_page
from projects.gap.gap import PLAYWRIGHT_HEADLESS

source = "target"
domain = "https://www.target.com"
PLAYWRIGHT_TIMEOUT = settings.playwright.timeout
PLAYWRIGHT_CONCURRENCY = settings.playwright.concurrency
PLAYWRIGHT_CONCURRENCY = 5
settings.save_login_state = False

from crawler.config import settings

FORMAT = "%(levelname)s %(asctime)s %(module)s %(lineno)d" " %(message)s %(filename)s %(name)s"

# 'format': '%(levelname)s %(asctime)s %(module)s %(lineno)d %(message)s %(pathname)s %(name)s'

logging.basicConfig(format=FORMAT, level=logging.DEBUG)
handler = logging.FileHandler(filename=settings.log_file_path.joinpath("target.log"), encoding="utf-8")

formatter = logging.Formatter(FORMAT)
handler.setFormatter(formatter)
log = logging.getLogger(__name__)
log.addHandler(handler)
# logger.addHandler(LogfireLoggingHandler())
log.info("日志配置成功")

ua = UserAgent(browsers=["edge", "chrome"])


async def run(playwright: Playwright) -> None:
    # 从playwright对象中获取chromium浏览器
    chromium = playwright.chromium
    # 指定代理
    # proxy = {"server": "http://127.0.0.1:7890"}
    # 启动chromium浏览器，开启开发者工具，非无头模式
    # browser = await chromium.launch(headless=False, devtools=True)
    proxy = {
        "server": settings.proxy_pool.server,
        "username": settings.proxy_pool.username,
        "password": settings.proxy_pool.password,
    }
    proxy = None
    user_data_dir = settings.user_data_dir
    if settings.save_login_state:
        context = await playwright.chromium.launch_persistent_context(
            user_data_dir,
            headless=PLAYWRIGHT_HEADLESS,
            proxy=proxy,
            # headless=False,
            # slow_mo=50,  # 每个操作的延迟时间（毫秒），便于调试
            # args=["--start-maximized"],  # 启动时最大化窗口
            # ignore_https_errors=True,  # 忽略HTTPS错误
            # devtools=True,  # 打开开发者工具
        )
    else:
        pass
    browser = await chromium.launch(
        headless=PLAYWRIGHT_HEADLESS,
        proxy=proxy,
        # devtools=True,
    )
    context = await browser.new_context()

    # 设置全局超时
    context.set_default_timeout(settings.playwright.timeout)
    # context.set_default_timeout(60000)
    # 创建一个新的浏览器上下文，设置视口大小
    # context = await browser.new_context(viewport={"width": 1920, "height": 1080})
    # 在浏览器上下文中打开一个新页面

    # 打开新的页面
    urls = [
        # ("women", "dresses", "https://www.target.com/c/dresses-women-s-clothing/-/N-5xtcg"),
        # ("women", "dresses", "black", "M", "https://www.target.com/c/dresses-women-s-clothing/-/N-5xtcgZvef8aZ5y761"),
        # (
        #     "women",
        #     "dresses",
        #     "black",
        #     "M",
        #     "https://www.target.com/c/dresses-women-s-clothing/-/N-5xtcgZvef8aZ5y761?Nao=24&moveTo=product-list-grid",
        # ),
        # (
        #     "women",
        #     "dresses",
        #     "https://www.target.com/c/dresses-women-s-clothing/-/N-5xtcg?Nao=48&moveTo=product-list-grid",
        # ),
        # ("women", "bottoms", "https://www.target.com/c/bottoms-women-s-clothing/-/N-txhdt"),
    ]
    for item in range(22, 38):
        urls.append(
            (
                "women",
                "dresses",
                "black",
                "M",
                f"https://www.target.com/c/dresses-women-s-clothing/-/N-5xtcgZvef8aZ5y761?Nao={24 * item}&moveTo=product-list-grid",
            ),
        )

    # 迭代类别urls
    for index, (primary_category, sub_category, color, size, base_url) in enumerate(urls):
        user_agent = ua.random
        context = await browser.new_context(user_agent=user_agent)
        log.info(f"当前UserAgent: {user_agent}")
        page = await context.new_page()
        async with page:
            # 拦截所有图片
            await page.route(
                "**/*",
                lambda route: route.abort() if route.request.resource_type == "image" else route.continue_(),
            )
            await page.goto(base_url)
            log.info(f"进入类别页面: {base_url=}")

            await page.wait_for_load_state(timeout=60000)
            # await page.wait_for_load_state("networkidle")
            await page.wait_for_timeout(3000)
            scroll_pause_time = random.randrange(500, 2500, 200)
            # await page.wait_for_timeout(1000)
            await scroll_page(page, scroll_pause_time=scroll_pause_time, step=2)
            # await page.pause()

            # 获取所有商品
            selector = '//*[@id="pageBodyContainer"]/div/div[1]/div/div[8]/div/div/div[1]/section/div/div/div/div/div[1]/div[2]/div/div/div[1]/div[1]/div[1]/a'
            product_locators = page.locator(selector)
            product_count = await product_locators.count()
            product_urls = []
            semaphore = asyncio.Semaphore(PLAYWRIGHT_CONCURRENCY)  # 设置并发请求数限制为10
            pdp_tasks = []
            for i in range(product_count):
                url = await product_locators.nth(i).get_attribute("href")
                print(url)
                url = url.replace(domain, "")
                url = domain + url
                product_urls.append(url)
                pdp_tasks.append(
                    open_pdp_page(
                        context,
                        url=url,
                        semaphore=semaphore,
                        source=source,
                        primary_category=primary_category,
                        sub_category=sub_category,
                        color=color,
                        size=size,
                    )
                )
            print(f"一共获取商品数: {len(product_urls)}")
            r = redis.from_url(settings.redis_dsn, decode_responses=True, protocol=3)
            async with r:
                if product_urls:
                    insert_numbers = await r.sadd(f"{source}:{primary_category}:{sub_category}:{color}", *product_urls)
                    log.info(f"添加{insert_numbers}条数据到redis中")
                else:
                    log.error(f"当前页面未获取到商品, 需要尝试切换IP, {base_url=}")

                log.debug(f"{product_urls}, {len(product_urls)}")

            result = await asyncio.gather(*pdp_tasks)

            r = redis.from_url(settings.redis_dsn, decode_responses=True, protocol=3)
            # 将商品加入商品索引中
            async with r:
                print(await r.get("a"))
                redis_key = f"target_index:{source}:{primary_category}:{sub_category}"
                print(redis_key)

                result = await r.sadd(redis_key, *product_urls) if product_urls else None
                print(result)


async def open_pdp_page(
    context: BrowserContext,
    *,
    url: str,
    semaphore: asyncio.Semaphore,
    # product_id: str | None = None,
    source: str,
    primary_category: str,
    sub_category: str,
    color: str | None = None,
    size: str | None = None,
):
    """
    打开产品详情页并
    :params:url: 产品url
    """
    async with semaphore:
        product_id = httpx.URL(url).path.split("/")[-1].split("-")[-1]
        sku_id = httpx.URL(url).params.get("preselect")
        log.info(f"通过PDP(产品详情页)URL获取商品id:{product_id=} SKU:{sku_id=}")
        r = redis.from_url(settings.redis_dsn, decode_responses=True, protocol=3)
        async with r:
            result = await r.get(f"status:{source}:{primary_category}:{sub_category}:{product_id}:{sku_id}")
            log.info(f"商品{product_id}, sku:{sku_id}, redis抓取状态标记: {result=}")
            if result == "done":
                log.warning(f"商品:{product_id=}, {sku_id}已抓取过, 跳过")
                return sku_id
        page = await context.new_page()
        page.set_default_timeout(PLAYWRIGHT_TIMEOUT)
        async with page:
            # 拦截所有图像
            # await page.route(
            #     "**/*",
            #     lambda route: route.abort() if route.request.resource_type == "image" else route.continue_(),
            # )

            # TODO 指定url

            review_status = None  # 评论抓取状态跟踪
            # product_id = None  # 从pdp页接口获取商品id
            product: dict | None = None

            product_event = asyncio.Event()
            review_event = asyncio.Event()
            skus_event = asyncio.Event()

            async def handle_review_route(route: Route):
                request = route.request
                # 等待商品接口获取到product_id 后再执行评论
                # await product_event.wait()
                # nonlocal product_id
                if "summary" in request.url:
                    r = redis.from_url(settings.redis_dsn, decode_responses=True, protocol=3)
                    async with r:
                        result = await r.get(f"review_status:{source}:{primary_category}:{sub_category}:{product_id}")
                        log.info(f"商品评论: {product_id} 评论, redis状态标记: {result=}")
                        log.info(f"拦截评论请求API:{route.request.url}")
                    if result != "done":
                        response = await route.fetch()
                        json_dict = await response.json()
                        # TODO  获取评论信息
                        reviews, total_count = parse_target_review_from_api(json_dict)
                        log.info(f"预期评论数{total_count}")
                        log.info(f"预期评论数{total_count}, reviews: , {len(reviews)}")
                        page_size = 50
                        total_pages = (total_count + page_size - 1) // page_size
                        log.info(f"总页数{total_pages}")

                        semaphore = asyncio.Semaphore(10)  # 设置并发请求数限制为5
                        tasks = []
                        reviews = []  # 该项目中需要清除默认8条
                        for i in range(0, total_pages):
                            review_url = (
                                httpx.URL(request.url).copy_set_param("page", i).copy_set_param("size", page_size)
                            )
                            print()
                            tasks.append(fetch_reviews(semaphore, review_url, request.headers))

                        new_reviews = await asyncio.gather(*tasks)
                        nonlocal review_status
                        for review in new_reviews:
                            if review is not None:
                                reviews.extend(review)
                            else:
                                review_status = "failed"
                                log.warning(f"评论获取失败: {review}")

                        log.info(f"实际评论数{len(reviews)}")
                        if review_status == "failed":
                            async with r:
                                await r.set(
                                    f"review_status:{source}:{primary_category}:{sub_category}:{product_id}", "failed"
                                )
                        else:
                            async with r:
                                log.info(f"商品评论{product_id}抓取完毕, 标记redis状态")
                                await r.set(
                                    f"review_status:{source}:{primary_category}:{sub_category}:{product_id}", "done"
                                )

                        review_event.set()
                        # with open("review.json", "w") as f:
                        #     # 使用orjson以支持datetime格式
                        #     f.write(orjson.dumps(reviews, option=orjson.OPT_NAIVE_UTC).decode("utf-8"))
                    else:
                        log.warning(f"商品[{product_id=}]的评论已抓取过, 跳过")
                        review_event.set()
                        # log.info("获取评论信息")
                        # with open(f"{settings.project_dir.joinpath('data', 'product_info')}/data-.json", "w") as f:
                        #     f.write(json.dumps(json_dict))
                        # pass
                # if "api" in request.pdp_url or "service" in request.pdp_url:
                #
                #     log.info(f"API Request URL: {request.pdp_url}")
                await route.continue_()

            async def handle_pdp_route(route: Route):
                request = route.request
                if "pdp_client" in request.url:
                    log.info(
                        f"拦截产品详情页API: {route.request.url}",
                    )
                    # TODO 获取产品信息
                    response = await route.fetch()
                    json_dict = await response.json()
                    nonlocal product
                    product = await parse_target_product(
                        json_dict,
                        primary_category=primary_category,
                        sub_category=sub_category,
                        source=source,
                        sku_id=sku_id,
                        product_id=product_id,
                        color=color,
                        size=size,
                        # cookies=cookies,
                        # headers=headers,
                    )
                    product_event.set()
                    log.info(f"商品详情: {product}")

                # if "pdp_variation_hierarchy" in request.url:
                #     log.info(f"拦截产品变体API: {route.request.url}")
                #     response = await route.fetch()
                #     json_dict = await response.json()
                #     skus = parse_target_product_variation(json_dict)
                #     skus_event.set()
                #     log.info(f"商品变体: {len(skus) if skus else 0}")
                await route.continue_()

            await page.route("**/r2d2.target.com/**", handle_review_route)

            await page.route("**/redsky.target.com/**", handle_pdp_route)
            # 导航到指定的URL
            # 其他操作...
            # 暂停执行
            response = await page.goto(url, timeout=PLAYWRIGHT_TIMEOUT)

            cookies_raw = await context.cookies(url)
            cookies = {cookie["name"]: cookie["value"] for cookie in cookies_raw}
            headers = response.headers

            # await page.pause()
            log.info("等待页面加载")
            # await page.wait_for_timeout(30000)
            # 滚动页面以加载评论
            scroll_pause_time = random.randrange(1000, 2500, 500)
            await scroll_page(page, scroll_pause_time)
            # 通过点击按钮加载评论
            # await page.locator('//*[@id="above-the-fold-information"]/div[2]/div/div/div/div[3]/button').click()

            await page.wait_for_load_state("load")  # 等待页面加载
            log.info("页面加载完成")

            # 或者等待某个selector 加载完成

            # await page.wait_for_timeout(1000)
            # await page.pause()

            # DOM中解析商品属性并下载商品图片并保存

            attributes = await parse_pdp_from_dom(page, sku_id=sku_id, cookies=cookies, headers=headers)

            await product_event.wait()
            # await skus_event.wait()
            await review_event.wait()
            if product:
                product.update(dict(attributes=attributes))
                save_product_data(product)
                product_status = "done"

            else:
                product_status = "faild"
                log.warning(f"商品{product_id=}, {sku_id=}未获取到产品信息,")
            # 保存产品信息到数据库
            # await page.pause()

            # fit_size 适合人群
            # TODO 当商品抓取完毕
            r = redis.from_url(settings.redis_dsn, decode_responses=True, protocol=3)

            async with r:
                log.info(f"商品{product_id=}, {sku_id=}抓取完毕, 标记redis状态")
                await r.set(f"status:{source}:{primary_category}:{sub_category}:{product_id}:{sku_id}", product_status)

            return sku_id


async def fetch_reviews(semaphore, url, headers):
    async with semaphore:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()  # 检查HTTP请求是否成功
            json_dict = response.json()
            return parse_target_review_from_api(json_dict)[0]


async def fetch_images(
    *,
    semaphore: asyncio.Semaphore,
    url: str,
    headers: dict | None = None,
    cookies: dict | None = None,
    file_path: Path | str,
    query_params: str = "?wid=2400&hei=2400&qlt=100&fmt=webp",
) -> bool:
    async with semaphore:
        try:
            start_time = asyncio.get_event_loop().time()
            async with httpx.AsyncClient(timeout=60) as client:
                log.debug(f"下载图片: {url}")
                response = await client.get(url + query_params, headers=headers, cookies=cookies)
                content_type = response.headers.get("Content-Type", "")
                if content_type.startswith("image"):
                    # image_basename = image_basename.split(".")[0]
                    extension = guess_extension(content_type)
                    log.info(f"图片类型{extension=}")
                else:
                    log.warning("非图片类型!")
                response.raise_for_status()  # 检查HTTP请求是否成功
                image_bytes = response.content
                with open(f"{str(file_path)}{extension}", "wb") as f:
                    f.write(image_bytes)
            end_time = asyncio.get_event_loop().time()
            log.debug(f"下载图片耗时: {end_time - start_time:.2f}s")
            return True
        except Exception as exc:
            log.error(f"下载图片失败, {exc=}")
            return False


def parse_target_review_from_api(
    data: dict, product_name: str | None = None, sku_id: str | None = None
) -> tuple[list, int]:
    reviews = data.get("reviews").get("results", []) if data.get("reviews") else []
    total_count = data.get("reviews").get("total_results", 0) if data.get("reviews") else []
    parsed_reviews = []
    log.info(f"评论数: {len(reviews)}")
    for review in reviews:
        # log.debug(f"评论ID : {review.get('id')}")
        photos = review.get("photos", None)
        parsed_review = dict(
            review_id=review.get("id", None),  # review_id
            proudct_name=product_name,  # TODO 该平台不存在
            title=review.get("title", None)[:128] if review.get("title") else None,
            comment=review.get("text", None)[:1024] if review.get("text") else None,
            photos=photos,
            outer_photos=photos,
            nickname=review.get("author", {}).get("nickname") if review.get("author", {}) else None,
            product_id=review.get("Tcin", None),
            # sku_id=review.get("product_variant", None) if review.get("details") else None,
            sku_id=None,  # TODO 该平台的评论没有sku_id
            helpful_votes=review.get("feedback").get("helpful", None)
            if review.get("feedback")
            else None,  # 点赞, 正面反馈数
            not_helpful_votes=review.get("feedback").get("unhelpful", None)
            if review.get("feedback")
            else None,  # 点踩, 负面反馈数
            inappropriate=review.get("feedback").get("inappropriate", None)
            if review.get("feedback")
            else None,  # 不合适 target 专用
            rating=review.get("Rating", None),  # 评分
            released_at=review.get("firstActivationDate", None),
            helpful_score=None,
            source="target",
            created_at=datetime.fromisoformat(review.get("submitted_at").replace("Z", "+00:00"))
            if review.get("submitted_at")
            else None,
            updated_at=datetime.fromisoformat(review.get("modified_at").replace("Z", "+00:00"))
            if review.get("modified_at")
            else None,
        )
        parsed_reviews.append(parsed_review)
        # TODO 下载评论
        if isinstance(photos, list):
            pass
    # 将评论保持到数据库
    save_review_data(parsed_reviews)
    return parsed_reviews, total_count


async def parse_pdp_from_dom(
    page: Page,
    *,
    cookies: dict | None = None,
    headers: dict | None = None,
    sku_id: str | None = None,
):
    # content = await page.content()
    # tree = etree.HTML(content)
    # product_name = tree.xpath('//*[@id="buy-box"]/div/h1/text()')[0]
    # product_name_locator = tree.xpath('//*[@id="buy-box"]/div/h1/h1/text()')
    # log.info(t, type(t))

    # TODO 下载图片

    product_name_locator = page.locator('//*[@id="buy-box"]/div/h1')
    if await product_name_locator.count() > 0:
        product_name = await product_name_locator.inner_text()
    else:
        product_name = None
    log.info(product_name)
    price_locator = page.locator('//*[@id="buy-box"]/div/div/div[1]/div[1]/span')
    if await price_locator.count() > 0:
        price = await price_locator.inner_text()
    else:
        price = None
    original_price_locator = page.locator("//*[@id='buy-box']/div/div/div[1]/div[1]/div/span")
    if await original_price_locator.count() > 0:
        original_price = await original_price_locator.inner_text()
    else:
        original_price = None
    log.info(f"{original_price=}")
    log.info(price)
    color_locator = page.locator("//*[@id='swatch-label--Color']/span[2]")
    if await color_locator.count() > 0:
        color = await color_locator.inner_text()
    else:
        color = None

    # TODO 通过页面获取产品属性
    try:
        await page.locator("//main/div/div[2]/div/div/div/div[3]/button").click()
        """#product-detail-tabs > div > div:nth-child(3) > button"""
        log.info("点击按钮成功")
    except Exception as exc:
        log.error(f"点击按钮失败: {exc}")
    size_locator = page.get_by_text(re.compile("Sizing: ", re.IGNORECASE))
    size = (await size_locator.first.inner_text()).split(": ")[-1] if await size_locator.count() > 0 else None
    print(f"{size=}")

    material_locator = page.get_by_text(re.compile("Material: ", re.IGNORECASE))
    material = (
        (await material_locator.first.inner_text()).split(": ")[-1] if await material_locator.count() > 0 else None
    )
    print(f"{material=}")

    garment_style_locator = page.get_by_text(re.compile("Garment Style: ", re.IGNORECASE))
    garment_style = (
        (await garment_style_locator.first.inner_text()).split(": ")[-1]
        if await garment_style_locator.count() > 0
        else ""
    )
    print(f"garment_style: {garment_style}")

    garment_length_locator = page.get_by_text(re.compile("Garment Length: ", re.IGNORECASE))
    garment_length = (
        (await garment_length_locator.first.inner_text()).split(": ")[-1]
        if await garment_length_locator.count() > 0
        else None
    )
    print(f"{garment_length=}")
    neckline_locator = page.get_by_text(re.compile("Neckline: ", re.IGNORECASE))
    neckline = (
        (await neckline_locator.first.inner_text()).split(": ")[-1] if await neckline_locator.count() > 0 else None
    )
    print(f"{neckline=}")
    fabric_name_locator = page.get_by_text(re.compile("Fabric Name: ", re.IGNORECASE))
    fabric_name = (
        (await fabric_name_locator.first.inner_text()).split(": ")[-1]
        if await fabric_name_locator.count() > 0
        else None
    )
    print(f"{fabric_name=}")

    total_garment_length_locator = page.get_by_text(re.compile("Total Garment Length: ", re.IGNORECASE))
    total_garment_length = (
        (await total_garment_length_locator.first.inner_text()).split(": ")[-1]
        if await total_garment_length_locator.count() > 0
        else None
    )
    print(f"{total_garment_length=}")

    garment_details_locator = page.get_by_text(re.compile("Garment Details: ", re.IGNORECASE))
    garment_details = (
        (await garment_details_locator.first.inner_text()).split(": ")[-1]
        if await garment_details_locator.count() > 0
        else None
    )
    print(f"{garment_details=}")

    pacage_quantity_locator = page.get_by_text(re.compile("Package Quantity: ", re.IGNORECASE))
    package_quantity = (
        (await pacage_quantity_locator.first.inner_text()).split(": ")[-1]
        if await pacage_quantity_locator.count() > 0
        else None
    )
    print(f"{package_quantity=}")

    garment_back_type_locator = page.get_by_text(re.compile("Garment Back Type: ", re.IGNORECASE))
    garment_back_type = (
        (await garment_back_type_locator.first.inner_text()).split(": ")[-1]
        if await garment_back_type_locator.count() > 0
        else None
    )
    print(f"{garment_back_type=}")

    fabric_weight_type_locator = page.get_by_text(re.compile("Fabric Weight Type: ", re.IGNORECASE))
    fabric_weight_type = (
        (await fabric_weight_type_locator.first.inner_text()).split(": ")[-1]
        if await fabric_weight_type_locator.count() > 0
        else None
    )
    print(f"{fabric_weight_type=}")

    garment_sleeve_style_locator = page.get_by_text(re.compile("Garment Sleeve Style: ", re.IGNORECASE))
    garment_sleeve_style = (
        (await garment_sleeve_style_locator.first.inner_text()).split(": ")[-1]
        if await garment_sleeve_style_locator.count() > 0
        else None
    )
    print(f"{garment_sleeve_style=}")

    care_and_cleaning_locator = page.get_by_text(re.compile("Care and Cleaning: ", re.IGNORECASE))
    care_and_cleaning = (
        (await care_and_cleaning_locator.first.inner_text()).split(": ")[-1]
        if await care_and_cleaning_locator.count() > 0
        else None
    )
    print(f"{care_and_cleaning=}")

    tcin_locator = page.get_by_text(re.compile("TCIN: ", re.IGNORECASE))
    tcin = (await tcin_locator.first.inner_text()).split(": ")[-1] if await tcin_locator.count() > 0 else None
    print(f"{tcin=}")

    upc_locator = page.get_by_text(re.compile("UPC: ", re.IGNORECASE))
    upc = (await upc_locator.first.inner_text()).split(": ")[-1] if await upc_locator.count() > 0 else None
    print(f"{upc=}")

    item_number_locator = page.get_by_text(re.compile("Item Number (DPCI): ", re.IGNORECASE))
    item_number = (
        (await item_number_locator.first.inner_text()).split(": ")[-1]
        if await item_number_locator.count() > 0
        else None
    )
    print(f"{item_number=}")

    origin_locator = page.get_by_text(re.compile("Origin: ", re.IGNORECASE))
    origin = (await origin_locator.first.inner_text()).split(": ")[-1] if await origin_locator.count() > 0 else None
    print(f"{origin=}")

    attributes = dict(
        size=size,
        material=material,
        garment_style=garment_style,
        garment_length=garment_length,
        neckline=neckline,
        fabric_name=fabric_name,
        total_garment_length=total_garment_length,
        garment_details=garment_details,
        package_quantity=package_quantity,
        garment_back_type=garment_back_type,
        fabric_weight_type=fabric_weight_type,
        garment_sleeve_style=garment_sleeve_style,
        care_and_cleaning=care_and_cleaning,
        tcin=tcin,
        upc=upc,
        item_number=item_number,
        origin=origin,
    )
    return attributes
    pass


async def parse_target_product(
    data: dict,
    sku_id: str | None = None,
    product_id: str | None = None,
    source: str | None = "target",
    primary_category: str | None = None,
    sub_category: str | None = None,
    color: str | None = None,
    size: str | None = None,
    headers: dict | None = None,
    cookies: dict | None = None,
) -> dict | None:
    """
    解析target商品信息
    """
    product: dict | None = data.get("data").get("product") if data.get("data") else {}
    if not product:
        log.error("未从接口中")
        return None
    product_id_from_api = product.get("tcin")
    if product_id_from_api != product_id:
        log.error(f"严重错误! 从接口中获取到的{product_id_from_api=}, 与从url中获取的{product_id=}不同")
        raise ValueError(f"严重错误! 从接口中获取到的{product_id_from_api=}, 与从url中获取的{product_id=}不同")
    category = (
        # product.get("category").get("parent_category_id", "") + " " + product.get("category").get("name", "")
        product.get("category").get("name", "") if product.get("category") else None
    )
    rating = (
        product.get("ratings_and_reviews").get("statistics").get("rating").get("average")
        if product.get("ratings_and_reviews")
        else None
    )
    rating_count = (
        product.get("ratings_and_reviews").get("statistics").get("rating").get("count")
        if product.get("ratings_and_reviews")
        else None
    )
    review_count = (
        product.get("ratings_and_reviews").get("statistics").get("review_count")
        if product.get("ratings_and_reviews")
        else None
    )
    product_url = product.get("item").get("enrichment").get("buy_url") if product.get("item") else None

    children: list[dict] = product.get("children", [])
    found = False
    image_urls = []
    for child in children:
        if child.get("tcin") == sku_id:
            image_url = (
                child.get("item").get("enrichment").get("images").get("primary_image_url") if child.get("item") else []
            )
            alternate_image_urls = (
                child.get("item").get("enrichment").get("images").get("alternate_image_urls", [])
                if child.get("item")
                else []
            )
            image_urls = [image_url] + alternate_image_urls if image_url else alternate_image_urls
            found = True
            break

    if not found:
        image_url = (
            product.get("item").get("enrichment").get("images").get("primary_image_url")
            if product.get("item")
            else None
        )
        alternate_image_urls = (
            product.get("item").get("enrichment").get("images").get("alternate_image_urls", [])
            if product.get("item")
            else []
        )
        image_urls = [image_url] + alternate_image_urls if image_url else alternate_image_urls

    r = redis.from_url(settings.redis_dsn, decode_responses=True, protocol=3)
    async with r:
        image_status = await r.get(
            f"image_download_status:{source}:{primary_category}:{sub_category}:{product_id}:{sku_id}"
        )
        if image_status == "done":
            log.warning(f"商品: {product_id}, sku:{sku_id}, 图片下载状态: {image_status}, 跳过")
        else:
            image_tasks = []
            semaphore = asyncio.Semaphore(10)  # 设置并发请求数限制为10
            sku_dir = settings.data_dir.joinpath(source, primary_category, sub_category, str(product_id), str(sku_id))
            sku_model_dir = sku_dir.joinpath("model")
            sku_model_dir.mkdir(parents=True, exist_ok=True)
            for index, url in enumerate(image_urls):
                log.info(f"图片{url=}")
                image_tasks.append(
                    fetch_images(
                        semaphore=semaphore,
                        url=url,
                        # headers=headers,
                        # cookies=cookies,
                        file_path=sku_model_dir.joinpath(f"model-{(index + 1):02d}-{url.split('/')[-1]}"),
                    )
                )

            image_download_status = await asyncio.gather(*image_tasks)
            if all(image_download_status) and len(image_download_status) > 0:
                r = redis.from_url(settings.redis_dsn, decode_responses=True, protocol=3)
                async with r:
                    await r.set(
                        f"image_download_status:{source}:{primary_category}:{sub_category}:{product_id}:{sku_id}",
                        "done",
                    )
                    log.warning(f"商品图片: {product_id}, sku:{sku_id}, 图片下载完成, 标记状态为done")
            else:
                log.warning(f"商品图片: {product_id}, sku:{sku_id}, 图片下载失败, 标记为failed")
                r = redis.from_url(settings.redis_dsn, decode_responses=True, protocol=3)
                async with r:
                    await r.set(
                        f"image_download_status:{source}:{primary_category}:{sub_category}:{product_id}:{sku_id}",
                        "failed",
                    )
                log.warning("商品图片抓取失败")
    product_name = product.get("item").get("product_description").get("title")[:128] if product.get("item") else None
    attributes = product.get("item").get("product_description").get("bullet_descriptions")
    price = product.get("price").get("formatted_current_price") if product.get("price") else None
    brand = product.get("item").get("primary_brand").get("name") if product.get("item") else None
    product_obj = dict(
        product_id=product_id,  # 商品ID
        sku_id=sku_id,  # sku_id
        product_name=product_name,  # 产品名称
        category=category,  # 类别
        rating=rating,  # 评分
        rating_count=rating_count,  # 评分数
        brand=brand,  # 品牌
        product_url=product_url,  # 商品链接
        image_url=image_url,  # 商品图片
        outer_image_url=image_url,
        price=price,  # 价格
        size=size,
        color=color,
        source=source,  # 来源
        model_image_url=alternate_image_urls[0] if len(alternate_image_urls) > 0 else None,
        outer_model_image_url=alternate_image_urls[0] if len(alternate_image_urls) > 0 else None,
        model_image_urls=image_urls,
        outer_model_image_urls=image_urls,
        # attributes=attributes,  # 弃用
        review_count=review_count,  # 评论数
        gender=primary_category,  # 大类别
        inner_category=sub_category,  # 内部类别
        sub_category=sub_category,  # 子类别
    )
    # 保存产品信息到数据库
    return product_obj
    pass


def parse_target_product_variation(data: dict) -> list[dict] | None:
    """
    解析target商品变体信息
    示例url
    https://redsky.target.com/redsky_aggregations/v1/web/pdp_variation_hierarchy_v1?key=9f36aeafbe60771e321a7cc95a78140772ab3e96&tcin=89766757&scheduled_delivery_store_id=1771&store_id=1771&latitude=41.9831&longitude=-91.6686&zip=52404&state=IA&visitor_id=018FBCFF654F0201A835C6E19137AC6F&channel=WEB&page=%2Fp%2FA-89766757
    """
    product: dict = data.get("data").get("product") if data.get("data") else None
    if not product:
        return None
    product_id = product.get("tcin") if product.get("tcin") else None
    size_layers: list = product.get("variation_hierarchy", [])
    skus = []
    for size_layer in size_layers:
        size = size_layer.get("value")
        color_layers: list = size_layer.get("variation_hierarchy", [])
        for color_layer in color_layers:
            color = color_layer.get("value")
            sku_id = color_layer.get("tcin")
            sku_url = color_layer.get("buy_url")
            image_url = color_layer.get("primary_image_url")
            sku = dict(
                product_id=product_id,  # 商品ID
                sku_id=sku_id,  # sku_id
                sku_url=sku_url,  # sku链接
                image_url=image_url,  # 图片链接
                sku_name=color,  # sku名称
                color=color,  # 颜色
                size=size,  # 尺寸
                source="target",  # 来源
            )
            skus.append(sku)
    # 将商品SKU保存到数据库
    # save_sku_data(skus)
    return skus

    pass


def map_attribute_field(input: dict) -> dict:
    """
    映射属性字段
    """
    # TODO 字段
    # input.get()

    return input

    pass


# async def scroll_page(page: Page, scroll_pause_time: int = 1000):
#     viewport_height = await page.evaluate("window.innerHeight")
#     i = 0
#     current_scroll_position = 0
#     while True:
#         # 滚动视口高度
#         i += 1
#         # log.info(f"第{i}次滚动, 滚动高度: {viewport_height}")
#         current_scroll_position += viewport_height
#         # log.info(f"当前滚动位置: {current_scroll_position}")
#         # 滚动到新的位置
#         await page.evaluate(f"window.scrollTo(0, {current_scroll_position})")
#         # 滚动到页面底部
#         # await page.evaluate(f"window.scrollTo(0, document.body.scrollHeight)")
#         await asyncio.sleep(scroll_pause_time / 1000)
#         # await page.wait_for_timeout(scroll_pause_time)
#         await page.wait_for_load_state("domcontentloaded")
#         # 重新获取页面高度
#         scroll_height = await page.evaluate("document.body.scrollHeight")
#         # 获取当前视口位置
#         current_viewport_position = await page.evaluate("window.scrollY + window.innerHeight")
#         # log.info(f"页面高度: {scroll_height}")
#         # log.info(f"当前视口位置: {current_viewport_position}")
#
#         if current_viewport_position >= scroll_height or current_scroll_position >= scroll_height:
#             # log.info("滚动到底部")
#             break
#         # previous_height = new_height


async def main():
    # 创建一个playwright对象并将其传递给run函数
    async with async_playwright() as p:
        await run(p)
        ...


# 这是脚本的入口点。
# 它开始执行main函数。
if __name__ == "__main__":
    # 指定本地代理
    asyncio.run(main())
