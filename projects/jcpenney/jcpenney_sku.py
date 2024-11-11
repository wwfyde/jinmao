import asyncio
import json
import os
from concurrent.futures import ProcessPoolExecutor

import httpx
import redis.asyncio as redis

from playwright.async_api import (
    async_playwright,
    BrowserContext,
    Route,
    TimeoutError as PlaywrightTimeoutError,
)

from crawler.config import settings
from crawler.deps import get_logger
from crawler.store import save_product_detail_data_async, save_product_data_async, \
    save_review_data_async, save_sku_data_async

PLAYWRIGHT_TIMEOUT = settings.playwright.timeout
IMAGE_POSTFIX = "?hei=1500&wid=1500&op_usm=.4%2C.8%2C0%2C0&resmode=sharp2&op_sharpen=1"
image_max_params = "?hei=1500&wid=1500&resmode=sharp2&op_sharpen=1"
PLAYWRIGHT_HEADLESS = settings.playwright.headless
PLAYWRIGHT_HEADLESS = False
log = get_logger("jcpenney")
source = 'jcpenney'


async def run(
        main_categories: str,
        sub_categories: str,
        *,
        should_use_proxy: bool = False,
        should_persistent_content: bool = False,
) -> None:
    async with async_playwright() as playwright:
        chromium = playwright.chromium
        # 是否使用
        if should_use_proxy:
            proxy = {
                "server": settings.proxy_pool.server,
                "username": settings.proxy_pool.username,
                "password": settings.proxy_pool.password,
            }
        else:
            proxy = None
        log.info(f"使用代理 {should_use_proxy=}")
        browser = await chromium.launch(
            # slow_mo=50, 
            headless=PLAYWRIGHT_HEADLESS,
            # args=["--single-process"], timeout=60000,
            # proxy=proxy,

        )
        context = await browser.new_context()

        if should_persistent_content:
            # 从配置中获取用户数据目录
            user_data_dir = settings.user_data_dir
            context = await chromium.launch_persistent_context(
                user_data_dir,
                headless=False,
                slow_mo=50,  # 每个操作的延迟时间（毫秒），便于调试
                args=["--single-process"],  # 启动时最大化窗口
                ignore_https_errors=True,  # 忽略HTTPS错误
                devtools=True,
            )

            # 设置全局超时
        semaphore = asyncio.Semaphore(settings.playwright.concurrency or 10)

        tasks = []
        log.info(f"开始抓取 {main_categories=} {sub_categories=}")
        pool = redis.ConnectionPool.from_url(settings.redis_dsn, decode_responses=True, protocol=3,
                                             max_connections=1000)
        r = redis.Redis(connection_pool=pool, decode_responses=True, protocol=3)
        key = f"{source}:{main_categories}:{sub_categories}"
        # 判断类别是否抓取完毕

        async with r:
            status = await r.get(f"category_task_status:{source}:{main_categories}:{sub_categories}")
            if status == "done":
                log.info(f"类别{main_categories}-{sub_categories}已经抓取过")
                return
            product_urls = await r.smembers(key)
            log.info(f"类别: {main_categories}-{sub_categories}, 共获取到 {len(product_urls)} 个商品链接")

        # 手动处理
        # product_urls = ['https://www.jcpenney.com/p/mutual-weave-mens-stretch-fabric-slim-fit-jean/ppr5008150388']
        for url in product_urls:
            tasks.append(
                open_pdp_page(
                    context,
                    semaphore,
                    url=url,
                    main_category=main_categories,
                    sub_category=sub_categories,
                    r=r
                )
            )

        task_results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in task_results:
            if isinstance(result, Exception):
                log.error(f"{result}")
        log.info(f"抓取完成 {main_categories=} {sub_categories=}")
        # 使用redis标记类别抓取状态, 避免再次扫描
        async with r:
            await r.set(f"category_task_status:{source}:{main_categories}:{sub_categories}", "done")
        await context.close()


async def open_pdp_page(
        context: BrowserContext,
        semaphore: asyncio.Semaphore,
        url: str,
        *,
        source: str = "jcpenney",
        main_category: str = None,
        sub_category: str = None,
        r: redis.Redis = None,
):
    async with semaphore:
        product_id = httpx.URL(url).path.split("/")[-1]  # 获取商品ID

        key = f"status:{source}:{product_id}"
        async with r:
            product_status = await r.get(key)
            if product_status == "done":
                log.info(f"已经抓取过产品 {product_id=}")
                return product_id
        page = await context.new_page()
        page.set_default_timeout(PLAYWRIGHT_TIMEOUT)

        # 临时储存商品信息目录
        product_folder = settings.data_dir.joinpath(source, "products")
        product_folder.mkdir(exist_ok=True, parents=True)
        product_file = product_folder.joinpath(f"product_{product_id}.json")
        # 临时储存评论目录
        reviews_folder = settings.data_dir.joinpath(source, "reviews")
        reviews_folder.mkdir(exist_ok=True, parents=True)
        reviews_file = reviews_folder.joinpath(f"reviews_{product_id}.json")

        # need_crawl = True
        # if Path(product_file).exists():
        #     log.info(f"已经抓取过产品 {product_id=}")
        #     need_crawl = False
        #     await page.wait_for_timeout(500)
        #     await page.close()
        #     return
        # 
        # need_review = True
        # if Path(reviews_file).exists():
        #     log.info(f"已经抓取过评论 {product_id=}")
        #     need_review = False
        # 
        # if not need_crawl and not need_review:
        #     await page.close()
        #     return

        # 声明路由事件
        async with page:
            # await cancel_requests(page)

            await page.route(
                "**/*",
                lambda route: route.abort() if route.request.resource_type == "image" else route.continue_(),
            )
            route_event = asyncio.Event()

            async def handle_route(route: Route):
                request = route.request
                # 处理用户评论
                if "reviews.json" in request.url:
                    async with r:
                        review_key = f"review_status:{source}:{product_id}"
                        review_status = await r.get(review_key)
                        if review_status == "done":
                            log.info(f"商品{product_id=}的评论已经抓取过, 抓取状态{review_status=}")
                            route_event.set()
                            return

                    response = await route.fetch()
                    reviews_dict = await response.json()
                    reviews, total_count = parse_reviews_from_api(reviews_dict)
                    page_size = 50
                    total_pages = (total_count + page_size - 1) // page_size

                    log.info(f"预期评论数{total_count}, 总页数{total_pages}")

                    # 翻页处理
                    review_semaphore = asyncio.Semaphore(3)  # 设置并发请求数限制为5
                    tasks = []
                    for i in range(1, total_pages + 1):
                        review_url = str(
                            httpx.URL(request.url)
                            .copy_set_param("limit", page_size)
                            .copy_set_param("offset", 8 + (i - 1) * page_size)
                        )
                        tasks.append(
                            fetch_reviews(review_semaphore, review_url, request.headers)
                        )

                    new_reviews = await asyncio.gather(*tasks, return_exceptions=True)
                    review_status = "done"
                    for review in new_reviews:
                        if isinstance(review, Exception):
                            log.error(f"尝试获取评论时出现了部分异常: {review}")
                            review_status = 'failed'
                            continue
                        elif isinstance(review, list):
                            reviews.extend(review)
                        else:
                            review_status = 'failed'
                            log.error(f"{review}")
                    # 保存评论
                    log.info(f"预期评论数{total_count}, 实际评论数{len(reviews)}")

                    await save_review_data_async(reviews)
                    # 保存到本地进行处理
                    async with r:
                        await r.set(review_key, review_status)
                        log.info(f"商品{product_id=}的评论已经抓取完成, 评论总数{total_count=}")

                    with open(reviews_file, "w", encoding="utf-8") as f:
                        f.write(json.dumps(reviews, indent=4, ensure_ascii=False))

                route_event.set()

            # await cancel_requests(page)
            await page.route("**/api.bazaarvoice.com/data/**", handle_route)

            await page.goto(
                url=url,
                timeout=PLAYWRIGHT_TIMEOUT,
            )

            # 从页面中获取产品详情信息
            preloaded_state: dict = await page.evaluate(
                """() => {
                                                        return window.__PRELOADED_STATE__;
                                                    }"""
            )
            if not preloaded_state:
                log.error(f"获取产品{product_id=}详情失败")
                return product_id

            sku_id = preloaded_state.get("queryParams", {}).get("selectedSKUId")

            try:
                lot_id_element = page.locator(
                    'div[data-automation-id="bazaar-voice"] + span'
                )
                await lot_id_element.wait_for(timeout=30000)
                lot_id = await lot_id_element.text_content()
            except PlaywrightTimeoutError:
                lot_id = None

            log.info(f"{sku_id=} {lot_id=}")

            with open(product_file, "w", encoding="utf-8") as f:
                f.write(json.dumps(preloaded_state, indent=4, ensure_ascii=False))

            # TODO 保存产品详情
            product_details = preloaded_state.get("productDetails")
            product: dict = dict(
                product_id=product_id,
                sku_id=sku_id,
                primary_sku_id=sku_id,
                source=source,
                gender=main_category if main_category not in (
                    'pets', 'furniture', 'household', 'outdoor-living-garden', 'jewelry-and-watches',
                    "home-store", "baby-kids", "toys-and-games", "shoes") else 'unknown',
                # 大类别,
                main_category=main_category,
                sub_category=sub_category,
                lot_id=lot_id,
            )

            if product_details:
                product_name = product_details.get("name")
                if product_name:
                    product_name = product_name[:128]
                domain = "https://www.jcpenney.com"
                brand = product_details.get("brand", {}).get("name")

                description = product_details.get("meta", {}).get("description")
                product_url = (
                    domain + product_details.get("meta", {}).get("canonicalUrl") if product_details.get("meta",
                                                                                                        {}) else None)
                category: str | None = product_details.get("category", {}).get("name")
                if category:
                    category = category.title()  # 转换为首字母大写

                rating = product_details.get("valuation", {}).get("rating")
                reviews = product_details.get("valuation", {}).get("reviews")
                review_count = reviews.get("count")

                category_breadcrumbs = product_details.get("breadCrumbInfo", {}).get(
                    "breadcrumbs", []
                )
                breadcrumbs = "/".join(
                    [
                        label.get("breadCrumbLabel").title()
                        for label in category_breadcrumbs
                        if label.get("breadCrumbLabel")
                    ]
                )

                product.update(
                    dict(
                        product_name=product_name,
                        brand=brand,
                        description=description,
                        product_url=product_url,
                        category=category,
                        rating=rating,
                        review_count=review_count,
                        category_breadcrumbs=breadcrumbs,
                    )
                )
                lots: list = product_details.get("lots", [])

                # 主图列表
                model_image_urls = [
                    url_item.get("url") + image_max_params
                    for url_item in product_details.get("images", [])
                    if url_item.get("url")
                ]
                if model_image_urls:
                    image_url = model_image_urls[0]
                else:
                    image_url = None
                product.update(
                    dict(
                        model_image_urls=model_image_urls,
                        outer_model_image_urls=model_image_urls,
                        image_url=image_url,
                        outer_image_url=image_url,
                    )
                )

                # 处理不同 SKU 内容
                for lot in lots:
                    if lot.get("id") == lot_id:
                        attributes = []
                        raw_attributes = lot.get("bulletedAttributes", [])
                        for raw_attribute in raw_attributes:
                            attributes.append(raw_attribute.get("description"))

                        if attributes:
                            product.update(dict(attributes=attributes, attributes_raw=attributes))

                        items = lot.get("items", [])
                        for item in items:
                            if item.get("id") == sku_id:
                                optionValues = item.get("optionValues", [])
                                size = item.get("size", None)
                                for value in optionValues:
                                    color = None
                                    size = None
                                    if "color" == value.get("name"):
                                        color = value.get("value")
                                    if value.get("name") == "size":
                                        size = value.get("value")

                                    product.update(dict(color=color, size=size))

                await save_product_data_async(product)
                await save_product_detail_data_async(product)
                await save_sku_data_async(product)
                log.info(f"已经保存产品数据 {product_id=}")
                async with r:
                    log.info(f"设置商品{product_id=}抓取状态为done")
                    await r.set(key, "done")
            else:
                log.warning(f"产品{product_id=}没有详情信息")

            # await page.wait_for_timeout(2000)
            # # 点击 Review button
            # review_button = page.locator("button#BVSummaryReviewBtn")
            # await review_button.wait_for(timeout=1000)
            # if review_button:
            #     await review_button.click()
            #     log.info("点击查看评论按钮完成")
            #     await page.wait_for_timeout(8000)
            try:
                # 最大等待三分钟
                await asyncio.wait_for(route_event.wait(), timeout=60 * 3)
            except TimeoutError as exc:
                log.error(f"商品{product_id=}, {url=}等待评论接口超时, {exc=}")
            await page.wait_for_timeout(3000)
            log.info(f"评论抓取完成 {product_id=}")
            log.info(f"关闭页面 {product_id=}")


def parse_reviews_from_api(data: dict, *, source: str = 'jcpenney') -> tuple[list, int]:
    """解析评论数据"""
    total_count = data.get("TotalResults", 0)
    reviews = data.get("Results", [])
    parsed_reviews = []
    for review in reviews:
        parsed_review = dict(
            review_id=review.get("Id", None),  # review_id
            # proudct_name=review.get("OriginalProductName", None),
            title=review.get("Title", None),
            comment=review.get("ReviewText", None),
            nickname=review.get("UserNickname", None),
            product_id=review.get("ProductId", None),
            sku_id=None,
            helpful_votes=review.get(
                "TotalPositiveFeedbackCount", 0
            ),  # 点赞, 正面反馈数
            not_helpful_votes=review.get(
                "TotalNegativeFeedbackCount", 0
            ),  # 点踩, 负面反馈数
            rating=review.get("Rating", None),
            released_at=review.get("firstActivationDate", None),
            helpful_score=None,
            source=source,
        )
        parsed_reviews.append(parsed_review)
    return parsed_reviews, total_count


async def fetch_reviews(semaphore, url, headers):
    """获取评论数据"""
    async with semaphore:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()  # 检查HTTP请求是否成功
            json_dict = response.json()
            return parse_reviews_from_api(json_dict)[0]


async def main():
    loop = asyncio.get_running_loop()
    num_processes = os.cpu_count() // 2
    num_processes = 2

    log.info(f"CPU核心数: {os.cpu_count()}, 进程数: {num_processes}")
    categories = [
        # ("men", "default"),
        ("men", "shirts"),
    ]
    categories = {
        ('women', 'view-all-women',
         'https://www.jcpenney.com/g/women/view-all-women?new_arrivals=view+all+new&id=cat10011030002&boostIds=ppr5008270089-ppr5008270103-ppr5008270088-ppr5008270067-ppr5008270073-ppr5008270107-ppr5008270565-ppr5008270075&cm_re=ZA-_-DEPARTMENT-WOMEN-_-LF-_-NEW-ARRIVALS-_-VIEW-ALL-WOMENS-NEW-ARRIVALS_1'),
        ('women', 'womens-plus-size',
         'https://www.jcpenney.com/g/women/womens-plus-size?id=cat1009580001&cm_re=ZB-_-DEPARTMENT-WOMEN-_-LF-_-SPECIAL-SIZES-_-PLUS_1'),
        ('women', 'women',
         'https://www.jcpenney.com/g/women?womens_size_range=petite&id=dept20000013&cm_re=ZB-_-DEPARTMENT-WOMEN-_-LF-_-SPECIAL-SIZES-_-PETITES-54-UNDER_2'),
        ('women', 'womens-tall',
         'https://www.jcpenney.com/g/women/womens-tall?id=cat1009600002&cm_re=ZB-_-DEPARTMENT-WOMEN-_-LF-_-SPECIAL-SIZES-_-TALL-510-UP_3'),
        ('women', 'maternity',
         'https://www.jcpenney.com/g/women/maternity?id=cat1009620002&cm_re=ZB-_-DEPARTMENT-WOMEN-_-LF-_-SPECIAL-SIZES-_-MATERNITY_4'),
        ('women', 'juniors',
         'https://www.jcpenney.com/d/juniors?cm_re=ZB-_-DEPARTMENT-WOMEN-_-LF-_-SPECIAL-SIZES-_-JUNIORS_5'), (
            'women', 'womens-dresses',
            'https://www.jcpenney.com/g/women/womens-dresses?id=cat100210008&cm_re=ZC-_-DEPARTMENT-WOMEN-_-LF-_-WOMENS-_-DRESSES_1'),
        ('women', 'womens-tops',
         'https://www.jcpenney.com/g/women/womens-tops?id=cat100210006&cm_re=ZC-_-DEPARTMENT-WOMEN-_-LF-_-WOMENS-_-TOPS_2'),
        ('women', 'womens-pants',
         'https://www.jcpenney.com/g/women/womens-pants?id=cat100250095&cm_re=ZC-_-DEPARTMENT-WOMEN-_-LF-_-WOMENS-_-PANTS_3'),
        ('women', 'lingerie',
         'https://www.jcpenney.com/d/women/lingerie?cm_re=ZC-_-DEPARTMENT-WOMEN-_-LF-_-WOMENS-_-BRAS-PANTIES-LINGERIE_4'),
        ('women', 'womens-coats',
         'https://www.jcpenney.com/g/women/womens-coats?id=cat100250094&cm_re=ZC-_-DEPARTMENT-WOMEN-_-LF-_-WOMENS-_-COATS-JACKETS_5'),
        ('women', 'womens-sweaters-cardigans',
         'https://www.jcpenney.com/g/women/womens-sweaters-cardigans?id=cat100210007&cm_re=ZC-_-DEPARTMENT-WOMEN-_-LF-_-WOMENS-_-SWEATERS-CARDIGANS_6'),
        ('women', 'womens-jeans',
         'https://www.jcpenney.com/g/women/womens-jeans?id=cat100250096&cm_re=ZC-_-DEPARTMENT-WOMEN-_-LF-_-WOMENS-_-JEANS_7'),
        ('women', 'womens-activewear',
         'https://www.jcpenney.com/g/women/womens-activewear?id=cat100250100&cm_re=ZC-_-DEPARTMENT-WOMEN-_-LF-_-WOMENS-_-ACTIVEWEAR_8'),
        ('women', 'womens-suits-work-dresses',
         'https://www.jcpenney.com/g/women/womens-suits-work-dresses?id=cat100260321&cm_re=ZC-_-DEPARTMENT-WOMEN-_-LF-_-WOMENS-_-SUITS-SUIT-SEPARATES_9'),
        ('women', 'womens-pajamas-bathrobes',
         'https://www.jcpenney.com/g/women/womens-pajamas-bathrobes?id=cat1003610003&cm_re=ZC-_-DEPARTMENT-WOMEN-_-LF-_-WOMENS-_-PAJAMAS-ROBES_10'),
        ('women', 'womens-skirts',
         'https://www.jcpenney.com/g/women/womens-skirts?id=cat100250097&cm_re=ZC-_-DEPARTMENT-WOMEN-_-LF-_-WOMENS-_-SKIRTS_11'),
        ('women', 'womens-swimsuits',
         'https://www.jcpenney.com/g/women/womens-swimsuits?id=cat100250101&cm_re=ZC-_-DEPARTMENT-WOMEN-_-LF-_-WOMENS-_-SWIMSUITS-COVER-UPS_12'),
        ('women', 'jumpsuits-rompers',
         'https://www.jcpenney.com/g/women/jumpsuits-rompers?id=cat1003860080&cm_re=ZC-_-DEPARTMENT-WOMEN-_-LF-_-WOMENS-_-JUMPSUITS-ROMPERS_13'),
        ('women', 'womens-shorts',
         'https://www.jcpenney.com/g/women/womens-shorts?id=cat100250098&cm_re=ZC-_-DEPARTMENT-WOMEN-_-LF-_-WOMENS-_-SHORTS_14'),
        ('women', 'womens-jackets-blazers',
         'https://www.jcpenney.com/g/women/womens-jackets-blazers?id=cat1003500018&cm_re=ZC-_-DEPARTMENT-WOMEN-_-LF-_-WOMENS-_-BLAZERS_15'),
        ('women', 'womens-leggings',
         'https://www.jcpenney.com/g/women/womens-leggings?id=cat100440108&cm_re=ZC-_-DEPARTMENT-WOMEN-_-LF-_-WOMENS-_-LEGGINGS_16'),
        ('women', 'capris-crops',
         'https://www.jcpenney.com/g/women/capris-crops?id=cat1007530006&cm_re=ZC-_-DEPARTMENT-WOMEN-_-LF-_-WOMENS-_-CAPRIS-CROPS_17'),
        ('women', 'womens-scrubs',
         'https://www.jcpenney.com/g/women/womens-scrubs?id=cat1001660002&cm_re=ZC-_-DEPARTMENT-WOMEN-_-LF-_-WOMENS-_-SCRUBS-WORKWEAR_18'),
        ('women', 'socks-hosiery-tights',
         'https://www.jcpenney.com/g/purses-accessories/socks-hosiery-tights?id=cat100640310&cm_re=ZC-_-DEPARTMENT-WOMEN-_-LF-_-WOMENS-_-SOCKS-HOSIERY-TIGHTS_19'),
        ('women', 'plus-dresses',
         'https://www.jcpenney.com/g/women/plus-dresses?id=cat1009690002&cm_re=ZD-_-DEPARTMENT-WOMEN-_-LF-_-PLUS-SIZE-_-DRESSES_1'),
        ('women', 'plus-tops',
         'https://www.jcpenney.com/g/women/plus-tops?id=cat1009690001&cm_re=ZD-_-DEPARTMENT-WOMEN-_-LF-_-PLUS-SIZE-_-TOPS_2'),
        ('women', 'womens-coats',
         'https://www.jcpenney.com/g/women/womens-coats?womens_size_range=plus&id=cat100250094&cm_re=ZD-_-DEPARTMENT-WOMEN-_-LF-_-PLUS-SIZE-_-COATS-JACKETS_3'),
        ('women', 'plus-pants',
         'https://www.jcpenney.com/g/women/plus-pants?id=cat1009690004&cm_re=ZD-_-DEPARTMENT-WOMEN-_-LF-_-PLUS-SIZE-_-PANTS_4'),
        ('women', 'plus-sweaters',
         'https://www.jcpenney.com/g/women/plus-sweaters?id=cat1009690005&cm_re=ZD-_-DEPARTMENT-WOMEN-_-LF-_-PLUS-SIZE-_-SWEATERS_5'),
        ('women', 'womens-activewear',
         'https://www.jcpenney.com/g/women/womens-activewear?womens_size_range=plus&id=cat100250100&cm_re=ZD-_-DEPARTMENT-WOMEN-_-LF-_-PLUS-SIZE-_-ACTIVEWEAR_6'),
        ('women', 'plus-jeans',
         'https://www.jcpenney.com/g/women/plus-jeans?id=cat1009690003&cm_re=ZD-_-DEPARTMENT-WOMEN-_-LF-_-PLUS-SIZE-_-JEANS_7'),
        ('women', 'womens-plus-size',
         'https://www.jcpenney.com/g/women/womens-plus-size?id=cat1009580001&cm_re=ZD-_-DEPARTMENT-WOMEN-_-LF-_-PLUS-SIZE-_-VIEW-ALL-PLUS_8'),
        ('women', 'all-womens-shoes',
         'https://www.jcpenney.com/g/shoes/all-womens-shoes?id=cat100240063&cm_re=ZE-_-DEPARTMENT-WOMEN-_-LF-_-SHOES-ACCESSORIES-_-SHOES_1'),
        ('women', 'womens-sandals-flip-flops',
         'https://www.jcpenney.com/g/shoes/womens-sandals-flip-flops?id=cat100250193&cm_re=ZE-_-DEPARTMENT-WOMEN-_-LF-_-SHOES-ACCESSORIES-_-SANDALS_2'),
        ('women', 'socks-hosiery-tights',
         'https://www.jcpenney.com/g/purses-accessories/socks-hosiery-tights?id=cat100640310&cm_re=ZE-_-DEPARTMENT-WOMEN-_-LF-_-SHOES-ACCESSORIES-_-SOCKS-HOSIERY-TIGHTS_3'),
        ('women', 'view-all-handbags-wallets',
         'https://www.jcpenney.com/g/purses-accessories/view-all-handbags-wallets?id=cat100250002&cm_re=ZE-_-DEPARTMENT-WOMEN-_-LF-_-SHOES-ACCESSORIES-_-HANDBAGS-WALLETS_4'),
        ('women', 'jewelry-and-watches',
         'https://www.jcpenney.com/d/jewelry-and-watches?cm_re=ZE-_-DEPARTMENT-WOMEN-_-LF-_-SHOES-ACCESSORIES-_-JEWELRY-WATCHES_5'),
        ('women', 'jcpenney-outfit-inspiration',
         'https://www.jcpenney.com/m/feature-shop/jcpenney-outfit-inspiration?cm_re=ZF-_-DEPARTMENT-WOMEN-_-LF-_-MORE-WAYS-TO-SHOP-_-TRENDING-NOW_1'),
        ('women', 'womens-essentials',
         'https://www.jcpenney.com/g/women/womens-essentials?id=cat11100010236&cm_re=ZF-_-DEPARTMENT-WOMEN-_-LF-_-MORE-WAYS-TO-SHOP-_-WOMENS-ESSENTIALS_2'),
        ('women', 'salon-haircare',
         'https://www.jcpenney.com/g/beauty/haircare/salon-haircare?id=cat11100005367&cm_re=ZF-_-DEPARTMENT-WOMEN-_-LF-_-MORE-WAYS-TO-SHOP-_-SALON_3'),
        ('women', 'jcpenney-beauty',
         'https://www.jcpenney.com/g/beauty/jcpenney-beauty?id=cat11100005471&cm_re=ZF-_-DEPARTMENT-WOMEN-_-LF-_-MORE-WAYS-TO-SHOP-_-BEAUTY_4'),
        ('women', 'ga-13+z-9516608059-2221311404',
         'https://www.jcpenney.comhttps://sportsfanshop.jcpenney.com/women/ga-13+z-9516608059-2221311404?_s=bm-JCP-DT-Dept-Women-left-nav&cm_re=ZF-_-DEPARTMENT-WOMEN-_-LF-_-MORE-WAYS-TO-SHOP-_-SPORTS-FAN-SHOP_5'),
        ('women', 'wedding-dress-shop',
         'https://www.jcpenney.com/g/women/wedding-dress-shop?id=cat1003070025&cm_re=ZF-_-DEPARTMENT-WOMEN-_-LF-_-MORE-WAYS-TO-SHOP-_-THE-WEDDING-SHOP_6'),
        ('women', '',
         'https://www.jcpenney.comhttp://www.jcpportraits.com/?cm_re=ZF-_-DEPARTMENT-WOMEN-_-LF-_-MORE-WAYS-TO-SHOP-_-JCP-PORTRAITS_7'),
        ('women', 'womens-activewear',
         'https://www.jcpenney.com/g/women/womens-activewear?brand=adidas&id=cat100250100&cm_re=ZG-_-DEPARTMENT-WOMEN-_-LF-_-BRANDS-_-ADIDAS_1'),
        ('women', 'women',
         'https://www.jcpenney.com/g/women?brand=alfred+dunner&id=dept20000013&cm_re=ZG-_-DEPARTMENT-WOMEN-_-LF-_-BRANDS-_-ALFRED-DUNNER_2'),
        ('women', 'ana',
         'https://www.jcpenney.com/g/shops/ana?id=cat10010660001&cm_re=ZG-_-DEPARTMENT-WOMEN-_-LF-_-BRANDS-_-A-N-A_3'),
        ('women', 'women',
         'https://www.jcpenney.com/g/women?brand=black+label+by+evan+picone&id=dept20000013&cm_re=ZG-_-DEPARTMENT-WOMEN-_-LF-_-BRANDS-_-BLACK-LABEL-BY-EVAN-PICONE_4'),
        ('women', 'bold-elements',
         'https://www.jcpenney.com/g/women/bold-elements?id=cat11100006383&cm_re=ZG-_-DEPARTMENT-WOMEN-_-LF-_-BRANDS-_-BOLD-ELEMENTS_5'),
        ('women', 'women',
         'https://www.jcpenney.com/g/women?brand=champion&id=dept20000013&cm_re=ZG-_-DEPARTMENT-WOMEN-_-LF-_-BRANDS-_-CHAMPION_6'),
        ('women', 'womens-frye-and-co',
         'https://www.jcpenney.com/g/women/womens-frye-and-co?id=cat11100007989&cm_re=ZG-_-DEPARTMENT-WOMEN-_-LF-_-BRANDS-_-FRYE-AND-CO_7'),
        ('women', 'gloria-vanderbilt',
         'https://www.jcpenney.com/g/shops/gloria-vanderbilt?id=cat10010300004&cm_re=ZG-_-DEPARTMENT-WOMEN-_-LF-_-BRANDS-_-GLORIA-VANDERBILT_8'),
        ('women', 'women',
         'https://www.jcpenney.com/g/women?brand=levi%27s&id=dept20000013&cm_re=ZG-_-DEPARTMENT-WOMEN-_-LF-_-BRANDS-_-LEVIS_9'),
        ('women', 'liz-claiborne',
         'https://www.jcpenney.com/g/women/liz-claiborne?id=cat11100001285&cm_re=ZG-_-DEPARTMENT-WOMEN-_-LF-_-BRANDS-_-LIZ-CLAIBORNE_10'),
        ('women', 'activewear',
         'https://www.jcpenney.com/g/women/activewear?brand=sports+illustrated&id=cat100250100&cm_re=ZG-_-DEPARTMENT-WOMEN-_-LF-_-BRANDS-_-SPORTS-ILLUSTRATED_11'),
        ('women', 'st-johns-bay-and-st-johns-bark',
         'https://www.jcpenney.com/g/women/st-johns-bay-and-st-johns-bark?id=cat1009430003&cm_re=ZG-_-DEPARTMENT-WOMEN-_-LF-_-BRANDS-_-ST-JOHNS-BAY_12'),
        ('women', 'stylus',
         'https://www.jcpenney.com/g/women/stylus?id=cat11100000392&cm_re=ZG-_-DEPARTMENT-WOMEN-_-LF-_-BRANDS-_-STYLUS_13'),
        ('women', 'women',
         'https://www.jcpenney.com/g/women?brand=worthington&id=dept20000013&cm_re=ZG-_-DEPARTMENT-WOMEN-_-LF-_-BRANDS-_-WORTHINGTON_14'),
        ('women', 'womens-activewear',
         'https://www.jcpenney.com/g/women/womens-activewear?brand=xersion&id=cat100250100&cm_re=ZG-_-DEPARTMENT-WOMEN-_-LF-_-BRANDS-_-XERSION_15'),
        ('women', 'women',
         'https://www.jcpenney.com/g/women?view_all=view+all+brands&id=dept20000013&cm_re=ZG-_-DEPARTMENT-WOMEN-_-LF-_-BRANDS-_-VIEW-ALL-BRANDS_16'),
        ('women', 'women',
         'https://www.jcpenney.com/g/women?s1_deals_and_promotions=SALE&id=dept20000013&cm_re=ZH-_-DEPARTMENT-WOMEN-_-LF-_-SALE-PROMOTIONS-_-SALE_1'),
        ('women', 'women',
         'https://www.jcpenney.com/g/women?s1_deals_and_promotions=CLEARANCE&id=dept20000013&cm_re=ZH-_-DEPARTMENT-WOMEN-_-LF-_-SALE-PROMOTIONS-_-CLEARANCE_2'),
        ('men', 'men',
         'https://www.jcpenney.com/g/men?new_arrivals=view+all+new&id=dept20000014&cm_re=ZA-_-DEPARTMENT-MEN-_-LF-_-VIEW-ALL-MENS-NEW-ARRIVALS_1'),
        ('men', 'mens-big-tall',
         'https://www.jcpenney.com/g/men/mens-big-tall?id=cat1009640001&cm_re=ZB-_-DEPARTMENT-MEN-_-LF-_-Mens_SizeRange_BigTall_1'),
        ('men', 'view-all-guys',
         'https://www.jcpenney.com/g/men/view-all-guys?id=cat100250145&cm_re=ZB-_-DEPARTMENT-MEN-_-LF-_-Mens_SizeRange_YoungMens_2'),
        ('men', 'workout-clothes',
         'https://www.jcpenney.com/g/men/workout-clothes?id=cat100290088&cm_re=ZC-_-DEPARTMENT-MEN-_-LF-_-Mens_Clothing_Activewear_1'),
        ('men', 'mens-coats-jackets',
         'https://www.jcpenney.com/g/men/mens-coats-jackets?id=cat100290087&cm_re=ZC-_-DEPARTMENT-MEN-_-LF-_-Mens_Clothing_CoatsJackets_2'),
        ('men', 'dress-clothes',
         'https://www.jcpenney.com/g/men/dress-clothes?id=cat1009180004&cm_re=ZC-_-DEPARTMENT-MEN-_-LF-_-Mens_Clothing_DressClothes_3'),
        ('men', 'mens-dress-shirts-ties',
         'https://www.jcpenney.com/g/men/mens-dress-shirts-ties?id=cat100250013&cm_re=ZC-_-DEPARTMENT-MEN-_-LF-_-Mens_Clothing_DressShirts_4'),
        ('men', 'mens-graphic-tees',
         'https://www.jcpenney.com/g/men/mens-graphic-tees?id=cat1002990005&cm_re=ZC-_-DEPARTMENT-MEN-_-LF-_-Mens_Clothing_GraphicTees_5'),
        ('men', 'mens-jeans',
         'https://www.jcpenney.com/g/men/mens-jeans?id=cat100250010&cm_re=ZC-_-DEPARTMENT-MEN-_-LF-_-Mens_Clothing_Jeans_6'),
        ('men', 'mens-pajamas-robes',
         'https://www.jcpenney.com/g/men/mens-pajamas-robes?id=cat100290091&cm_re=ZC-_-DEPARTMENT-MEN-_-LF-_-Mens_Clothing_PajamasRobesSlippers_7'),
        ('men', 'mens-pants',
         'https://www.jcpenney.com/g/men/mens-pants?id=cat100250021&cm_re=ZC-_-DEPARTMENT-MEN-_-LF-_-Mens_Clothing_Pants_8'),
        ('men', 'mens-scrubs-workwear',
         'https://www.jcpenney.com/g/men/mens-scrubs-workwear?id=cat100290092&cm_re=ZC-_-DEPARTMENT-MEN-_-LF-_-SCRUBS-WORKWEAR_9'),
        ('men', 'mens-shirts',
         'https://www.jcpenney.com/g/men/mens-shirts?id=cat100240025&cm_re=ZC-_-DEPARTMENT-MEN-_-LF-_-Mens_Clothing_Shirts_10'),
        ('men', 'mens-shorts',
         'https://www.jcpenney.com/g/men/mens-shorts?id=cat100290085&cm_re=ZC-_-DEPARTMENT-MEN-_-LF-_-Mens_Clothing_Shorts_11'),
        ('men', 'mens-socks',
         'https://www.jcpenney.com/g/men/mens-socks?id=cat100290090&cm_re=ZC-_-DEPARTMENT-MEN-_-LF-_-Mens_Clothing_Socks_12'),
        ('men', 'mens-suits-sport-coats',
         'https://www.jcpenney.com/g/men/mens-suits-sport-coats?item_type=blazers%7Csport+coats&id=cat100250022&cm_re=ZC-_-DEPARTMENT-MEN-_-LF-_-Mens_Clothing_SportCoatsBlazers_13'),
        ('men', 'mens-suits-sport-coats',
         'https://www.jcpenney.com/g/men/mens-suits-sport-coats?id=cat100250022&cm_re=ZC-_-DEPARTMENT-MEN-_-LF-_-Mens_Clothing_SuitsSuitSeparates_14'),
        ('men', 'mens-sweaters',
         'https://www.jcpenney.com/g/men/mens-sweaters?id=cat100290045&cm_re=ZC-_-DEPARTMENT-MEN-_-LF-_-Mens_Clothing_Sweaters_15'),
        ('men', 'mens-hoodies',
         'https://www.jcpenney.com/g/men/mens-hoodies?id=cat100290079&cm_re=ZC-_-DEPARTMENT-MEN-_-LF-_-Mens_Clothing_SweatshirtsHoodies_16'),
        ('men', 'mens-swimwear',
         'https://www.jcpenney.com/g/men/mens-swimwear?id=cat100290086&cm_re=ZC-_-DEPARTMENT-MEN-_-LF-_-Mens_Clothing_Swimwear_17'),
        ('men', 'mens-underwear',
         'https://www.jcpenney.com/g/men/mens-underwear?id=cat100290089&cm_re=ZC-_-DEPARTMENT-MEN-_-LF-_-Mens_Clothing_Underwear_18'),
        ('men', 'belts-suspenders',
         'https://www.jcpenney.com/g/men/belts-suspenders?id=cat1009150001&cm_re=ZD-_-DEPARTMENT-MEN-_-LF-_-Mens_Accessories_BeltsSuspenders_1'),
        ('men', 'mens-hats',
         'https://www.jcpenney.com/g/men/mens-hats?id=cat11100007109&cm_re=ZD-_-DEPARTMENT-MEN-_-LF-_-HATS_2'), (
            'men', 'mens-jewelry',
            'https://www.jcpenney.com/g/jewelry-and-watches/mens-jewelry?id=cat100260183&cm_re=ZD-_-DEPARTMENT-MEN-_-LF-_-Mens_Accessories_MensJewelry_3'),
        ('men', 'mens-shoes',
         'https://www.jcpenney.com/g/shoes/mens-shoes?id=cat100300057&cm_re=ZD-_-DEPARTMENT-MEN-_-LF-_-Mens_Accessories_Shoes_4'),
        ('men', 'ties-bowties-pocket-squares',
         'https://www.jcpenney.com/g/men/ties-bowties-pocket-squares?id=cat1009020002&cm_re=ZD-_-DEPARTMENT-MEN-_-LF-_-Mens_Accessories_TiesBowTiesPocketSquares_5'),
        ('men', 'belts-wallets',
         'https://www.jcpenney.com/g/men/belts-wallets?id=cat1007640002&cm_re=ZD-_-DEPARTMENT-MEN-_-LF-_-Mens_Accessories_Wallets_6'),
        ('men', 'mens-watches',
         'https://www.jcpenney.com/g/jewelry-and-watches/mens-watches?id=cat1002300029&cm_re=ZD-_-DEPARTMENT-MEN-_-LF-_-Mens_Accessories_Watches_7'),
        ('men', 'view-all-accessories-for-men',
         'https://www.jcpenney.com/g/men/view-all-accessories-for-men?id=cat1004600024&cm_re=ZD-_-DEPARTMENT-MEN-_-LF-_-Mens_Accessories_ViewAllAccessories_8'),
        ('men', 'workout-clothes',
         'https://www.jcpenney.com/g/men/workout-clothes?id=cat100290088&cm_re=ZE-_-DEPARTMENT-MEN-_-LF-_-Mens_MoreWaysToShop_ActiveWellness_1'),
        ('men', 'men',
         'https://www.jcpenney.com/g/men?activity=golf&id=dept20000014&cm_re=ZE-_-DEPARTMENT-MEN-_-LF-_-Mens_MoreWaysToShop_GolfApparel_2'),
        ('men', 'mens-giftables',
         'https://www.jcpenney.com/g/men/mens-giftables?id=cat1009440001&cm_re=ZE-_-DEPARTMENT-MEN-_-LF-_-Mens_MoreWaysToShop_MensGifts_3'),
        ('men', 'outdoor-shop',
         'https://www.jcpenney.com/g/men/outdoor-shop?id=cat10010340001&cm_re=ZE-_-DEPARTMENT-MEN-_-LF-_-Mens_MoreWaysToShop_OutdoorShop_4'),
        ('men', 'ga-23+z-9253709466-4143417065',
         'https://www.jcpenney.comhttps://sportsfanshop.jcpenney.com/men/ga-23+z-9253709466-4143417065?_s=bm-JCP-DT-Dept-Men-left-nav&cm_re=ZE-_-DEPARTMENT-MEN-_-LF-_-Mens_MoreWaysToShop_SportsFanShop_5'),
        ('men', 'men',
         'https://www.jcpenney.com/g/men?brand=arizona&id=dept20000014&cm_re=ZF-_-DEPARTMENT-MEN-_-LF-_-Mens_Brands_Arizona_1'),
        ('men', 'men',
         'https://www.jcpenney.com/g/men?brand=champion&id=dept20000014&cm_re=ZF-_-DEPARTMENT-MEN-_-LF-_-Mens_Brands_Champion_2'),
        ('men', 'men',
         'https://www.jcpenney.com/g/men?brand=dockers&id=dept20000014&cm_re=ZF-_-DEPARTMENT-MEN-_-LF-_-Mens_Brands_Dockers_3'),
        ('men', 'mens-frye-and-co',
         'https://www.jcpenney.com/g/men/mens-frye-and-co?id=cat11100008007&cm_re=ZF-_-DEPARTMENT-MEN-_-LF-_-FRYE-AND-CO_4'),
        ('men', 'men',
         'https://www.jcpenney.com/g/men?brand=izod&id=dept20000014&cm_re=ZF-_-DEPARTMENT-MEN-_-LF-_-Mens_Brands_Izod_5'),
        ('men', 'men',
         'https://www.jcpenney.com/g/men?brand=j.ferrar&id=dept20000014&cm_re=ZF-_-DEPARTMENT-MEN-_-LF-_-J-FERRAR_6'),
        ('men', 'men',
         'https://www.jcpenney.com/g/men?gender=mens&brand=levi%27s&id=dept20000014&cm_re=ZF-_-DEPARTMENT-MEN-_-LF-_-Mens_Brands_Levis_7'),
        ('men', 'brand',
         'https://www.jcpenney.com/g/brand?brand=mutual+weave&cm_re=ZF-_-DEPARTMENT-MEN-_-LF-_-MUTUAL-WEAVE_8'), (
            'men', 'men',
            'https://www.jcpenney.com/g/men?brand=shaquille+o%27neal+xlg&id=dept20000014&cm_re=ZF-_-DEPARTMENT-MEN-_-LF-_-Mens_Brands_Shaquille-O-Neal_9'),
        ('men', 'men',
         'https://www.jcpenney.com/g/men?brand=st.+john%27s+bay&id=dept20000014&cm_re=ZF-_-DEPARTMENT-MEN-_-LF-_-Mens_Brands_SJB_10'),
        ('men', 'stafford',
         'https://www.jcpenney.com/g/shops/stafford?id=cat10010660003&cm_re=ZF-_-DEPARTMENT-MEN-_-LF-_-Mens_Brands_Stafford_11'),
        ('men', 'men',
         'https://www.jcpenney.com/g/men?brand=u.s.+polo+assn.&id=dept20000014&cm_re=ZF-_-DEPARTMENT-MEN-_-LF-_-U-S-POLO-ASSN_12'),
        ('men', 'men',
         'https://www.jcpenney.com/g/men?brand=van+heusen&id=dept20000014&cm_re=ZF-_-DEPARTMENT-MEN-_-LF-_-Mens_Brands_VanHeusen_13'),
        ('men', 'workout-clothes',
         'https://www.jcpenney.com/g/men/workout-clothes?brand=xersion&id=cat100290088&cm_re=ZF-_-DEPARTMENT-MEN-_-LF-_-Mens_Brands_Xersion_14'),
        ('men', 'view-all-mens-brands',
         'https://www.jcpenney.com/g/men/view-all-mens-brands?id=cat100290093&cm_re=ZF-_-DEPARTMENT-MEN-_-LF-_-Mens_Brands_ViewAllBrands_15'),
        ('men', 'men',
         'https://www.jcpenney.com/g/men?s1_deals_and_promotions=SALE&id=dept20000014&cm_re=ZG-_-DEPARTMENT-MEN-_-LF-_-Mens_SalePromotions_Sale_1'),
        ('men', 'men',
         'https://www.jcpenney.com/g/men?s1_deals_and_promotions=CLEARANCE&id=dept20000014&cm_re=ZG-_-DEPARTMENT-MEN-_-LF-_-Mens_SalePromotions_Clearance_2'),

        ("girls", "default", "https://www.jcpenney.com/g/baby-kids/all-girls-clothing?id=cat11100001191"),
        ("boys", "default", "https://www.jcpenney.com/g/baby-kids/all-boys-clothing?id=cat11100001196"),
    }
    categories = {('jewelry-and-watches', 'jewelry-and-watches',
                   'https://www.jcpenney.com/g/jewelry-and-watches?new_arrivals=view+all+new&id=dept20000020&cm_re=ZC-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-BLK-FRI-22-_-SHOP-ALL-JEWELRY-NEW-ARRIVALS_1'),
                  ('jewelry-and-watches', 'engagement-rings',
                   'https://www.jcpenney.com/g/jewelry-and-watches/engagement-rings?id=cat1009920002&cm_re=ZD-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_FineJewelry_EngagementRings_1'),
                  ('jewelry-and-watches', 'view-all-modern-bride',
                   'https://www.jcpenney.com/g/jewelry-and-watches/view-all-modern-bride?ring_style=wedding+bands&id=cat1004860021&cm_re=ZD-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_FineJewelry_WeddingBands_2'),
                  ('jewelry-and-watches', 'rings',
                   'https://www.jcpenney.com/g/jewelry-and-watches/rings?mktTiles=0&id=cat100240086&cm_re=ZD-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_FineJewelry_FineRings_3'),
                  ('jewelry-and-watches', 'earrings',
                   'https://www.jcpenney.com/g/jewelry-and-watches/earrings?mktTiles=0&id=cat100240094&cm_re=ZD-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_FineJewelry_FineEarrings_4'),
                  ('jewelry-and-watches', 'necklaces-pendants',
                   'https://www.jcpenney.com/g/jewelry-and-watches/necklaces-pendants?mktTiles=0&id=cat100240093&cm_re=ZD-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_FineJewelry_FineNecklaces_5'),
                  ('jewelry-and-watches', 'bracelets',
                   'https://www.jcpenney.com/g/jewelry-and-watches/bracelets?mktTiles=0&id=cat100240096&cm_re=ZD-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_FineJewelry_FineBracelets_6'),
                  ('jewelry-and-watches', 'fine-jewelry-sets',
                   'https://www.jcpenney.com/g/jewelry-and-watches/fine-jewelry-sets?mktTiles=0&id=cat100260194&cm_re=ZD-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_FineJewelry_FineJewelrySets_7'),
                  ('jewelry-and-watches', 'fine-jewelry',
                   'https://www.jcpenney.com/g/jewelry-and-watches/fine-jewelry?features=in+a+gift+box&mktTiles=0&id=cat100260192&cm_re=ZD-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_FineJewelry_RedBowDeals_8'),
                  ('jewelry-and-watches', 'fine-jewelry',
                   'https://www.jcpenney.com/g/jewelry-and-watches/fine-jewelry?mktTiles=0&id=cat100260192&cm_re=ZD-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_FineJewelry_AllFineJewelry_9'),
                  ('jewelry-and-watches', 'view-all-modern-bride',
                   'https://www.jcpenney.com/g/jewelry-and-watches/view-all-modern-bride?mktTiles=0&id=cat1004860021&cm_re=ZE-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_FeaturedCategories_WeddingJewelry_1'),
                  ('jewelry-and-watches', 'diamond-jewelry',
                   'https://www.jcpenney.com/g/jewelry-and-watches/diamond-jewelry?mktTiles=0&id=cat100260184&cm_re=ZE-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_FeaturedCategories_DiamondJewelry_2'),
                  ('jewelry-and-watches', 'birthstone-jewelry',
                   'https://www.jcpenney.com/g/jewelry-and-watches/birthstone-jewelry?id=cat10010020003&cm_re=ZE-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_FeaturedCategories_BirthstoneJewelry_3'),
                  ('jewelry-and-watches', 'gemstone-jewelry',
                   'https://www.jcpenney.com/g/jewelry-and-watches/gemstone-jewelry?id=cat1003050007&cm_re=ZE-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_FeaturedCategories_GemstoneJewelry_4'),
                  ('jewelry-and-watches', 'mens-jewelry',
                   'https://www.jcpenney.com/g/jewelry-and-watches/mens-jewelry?mktTiles=0&id=cat100260183&cm_re=ZE-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_FeaturedCategories_MensJewelry_5'),
                  ('jewelry-and-watches', 'fine-jewelry',
                   'https://www.jcpenney.com/g/jewelry-and-watches/fine-jewelry?age_group=kids&id=cat100260192&cm_re=ZE-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_FeaturedCategories_KidsJewelry_6'),
                  ('jewelry-and-watches', 'pearl-earrings-necklaces',
                   'https://www.jcpenney.com/g/jewelry-and-watches/pearl-earrings-necklaces?mktTiles=0&id=cat1003050008&cm_re=ZE-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_FeaturedCategories_PearlJewelry_7'),
                  ('jewelry-and-watches', 'gold-jewelry',
                   'https://www.jcpenney.com/g/jewelry-and-watches/gold-jewelry?id=cat100260186&cm_re=ZE-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_FeaturedCategories_GoldJewelry_8'),
                  ('jewelry-and-watches', 'silver-jewelry',
                   'https://www.jcpenney.com/g/jewelry-and-watches/silver-jewelry?id=cat100260187&cm_re=ZE-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_FeaturedCategories_SilverJewelry_9'),
                  ('jewelry-and-watches', 'fine-jewelry',
                   'https://www.jcpenney.com/g/jewelry-and-watches/fine-jewelry?mktTiles=0&id=cat100260192&stone=cubic+zirconia%7Cmoissanite&cm_re=ZE-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_FeaturedCategories_AlternativeDiamondJewelry_10'),
                  ('jewelry-and-watches', 'jewelry-and-watches',
                   'https://www.jcpenney.com/g/jewelry-and-watches?division=005&features=in+a+gift+box&id=dept20000020&cm_re=ZE-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_FeaturedCategories_BoxedJewelry_11'),
                  ('jewelry-and-watches', 'personalized-jewelry',
                   'https://www.jcpenney.com/d/jewelry-watches/personalized-jewelry?cm_re=ZE-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_FeaturedCategories_PersonalizedJewelry_12'),
                  ('jewelry-and-watches', 'jewelry-and-watches',
                   'https://www.jcpenney.com/g/jewelry-and-watches?features=religious+jewelry&id=dept20000020&cm_re=ZE-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_FeaturedCategories_ReligiousJewelry_13'),
                  ('jewelry-and-watches', 'charms-charm-bracelets',
                   'https://www.jcpenney.com/g/jewelry-and-watches/charms-charm-bracelets?id=cat10010990003&cm_re=ZE-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_FeaturedCategories_CharmsCharmBracelets_14'),
                  ('jewelry-and-watches', 'jewelry-armoires-boxes',
                   'https://www.jcpenney.com/g/jewelry-and-watches/jewelry-armoires-boxes?id=cat100250007&cm_re=ZE-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_FeaturedCategories_JewelryBoxesArmoires_15'),
                  ('jewelry-and-watches', 'fashion-necklaces-pendants',
                   'https://www.jcpenney.com/g/jewelry-and-watches/fashion-necklaces-pendants?mktTiles=0&id=cat100260188&cm_re=ZF-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_FashionJewelry_FashionNecklaces_1'),
                  ('jewelry-and-watches', 'fashion-earrings',
                   'https://www.jcpenney.com/g/jewelry-and-watches/fashion-earrings?mktTiles=0&id=cat100260190&cm_re=ZF-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_FashionJewelry_FashionEarrings_2'),
                  ('jewelry-and-watches', 'fashion-bracelets',
                   'https://www.jcpenney.com/g/jewelry-and-watches/fashion-bracelets?mktTiles=0&id=cat100260189&cm_re=ZF-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_FashionJewelry_FashionBracelets_3'),
                  ('jewelry-and-watches', 'fashion-rings',
                   'https://www.jcpenney.com/g/jewelry-and-watches/fashion-rings?mktTiles=0&id=cat100260191&cm_re=ZF-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_FashionJewelry_FashionRings_4'),
                  ('jewelry-and-watches', 'fashion-jewelry-sets',
                   'https://www.jcpenney.com/g/jewelry-and-watches/fashion-jewelry-sets?mktTiles=0&id=cat1002700041&cm_re=ZF-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_FashionJewelry_FashionJewelrySets_5'),
                  ('jewelry-and-watches', 'fashion-jewelry',
                   'https://www.jcpenney.com/g/jewelry-and-watches/fashion-jewelry?subdivision=058&mktTiles=0&id=cat100240091&cm_re=ZF-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_FashionJewelry_FashionSilver_6'),
                  ('jewelry-and-watches', 'fashion-jewelry',
                   'https://www.jcpenney.comhttps://www.jcpenney.com/g/jewelry-and-watches/fashion-jewelry?id=cat100240091&Nf=PR+1+10&cm_re=ZF-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_FashionJewelry_10AndUnder_7'),
                  ('jewelry-and-watches', 'fashion-jewelry',
                   'https://www.jcpenney.com/g/jewelry-and-watches/fashion-jewelry?id=cat100240091&cm_re=ZF-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_FashionJewelry_ViewAllFashionJewelry_8'),
                  ('jewelry-and-watches', 'mens-watches',
                   'https://www.jcpenney.com/g/jewelry-and-watches/mens-watches?mktTiles=0&id=cat1002300029&cm_re=ZG-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_Watches_MensWatches_1'),
                  ('jewelry-and-watches', 'womens-watches',
                   'https://www.jcpenney.com/g/jewelry-and-watches/womens-watches?mktTiles=0&id=cat1002300028&cm_re=ZG-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_Watches_WomensWatches_2'),
                  ('jewelry-and-watches', 'kids-watches',
                   'https://www.jcpenney.com/g/jewelry-and-watches/kids-watches?mktTiles=0&id=cat1002300030&cm_re=ZG-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_Watches_KidsWatches_3'),
                  ('jewelry-and-watches', 'jewelry-and-watches',
                   'https://www.jcpenney.com/g/jewelry-and-watches?item_type=fitness+trackers%7Csmart+watches&id=dept20000020&cm_re=ZG-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_Watches_ActiveSmartWatches_4'),
                  ('jewelry-and-watches', 'jewelry-and-watches',
                   'https://www.jcpenney.com/g/jewelry-and-watches?subdivision=051%7C060&mktTiles=0&id=dept20000020&cm_re=ZG-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_Watches_FineWatches_5'),
                  ('jewelry-and-watches', 'fashion-watches',
                   'https://www.jcpenney.com/g/jewelry-and-watches/fashion-watches?mktTiles=0&id=cat1003480102&cm_re=ZG-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_Watches_FashionWatches_6'),
                  ('jewelry-and-watches', 'all-watches',
                   'https://www.jcpenney.com/g/jewelry-and-watches/all-watches?id=cat100240089&Nf=PR+0.00+50.00&cm_re=ZG-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_Watches_50AndUnderWatches_7'),
                  ('jewelry-and-watches', 'all-watches',
                   'https://www.jcpenney.com/g/jewelry-and-watches/all-watches?mktTiles=0&id=cat100240089&cm_re=ZG-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_Watches_ViewAllWatches_8'),
                  ('jewelry-and-watches', 'name-initial-monogram',
                   'https://www.jcpenney.com/g/jewelry-and-watches/personalized-jewelry/name-initial-monogram?mktTiles=0&id=cat1005850002&cm_re=ZH-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_PersonalizedJewelry_NameInitialMonogram_1'),
                  ('jewelry-and-watches', 'artcarved-moms-jewelery',
                   'https://www.jcpenney.comhttps://personalizedjewelry.jcpenney.com/shop/category/artcarved-moms-jewelery?cm_re=ZH-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_PersonalizedJewelry_ArtcarvedMomJewelry_2'),
                  ('jewelry-and-watches', 'college-class-rings',
                   'https://www.jcpenney.comhttps://personalizedjewelry.jcpenney.com/shop/category/college-class-rings?cm_re=ZH-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_PersonalizedJewelry_ArtcarvedClassRings_3'),
                  ('jewelry-and-watches', 'couples-and-commitment',
                   'https://www.jcpenney.comhttps://personalizedjewelry.jcpenney.com/shop/category/couples-and-commitment?cm_re=ZH-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_PersonalizedJewelry_CouplesCommitmentRings_4'),
                  ('jewelry-and-watches', 'family-jewelry',
                   'https://www.jcpenney.com/g/jewelry-and-watches/personalized-jewelry/family-jewelry?mktTiles=0&id=cat1005820003&cm_re=ZH-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_PersonalizedJewelry_Family_5'),
                  ('jewelry-and-watches', 'military-and-service',
                   'https://www.jcpenney.comhttps://personalizedjewelry.jcpenney.com/shop/theme/military-and-service?cm_re=ZH-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_PersonalizedJewelry_ArtcarvedMilitaryService_6'),
                  ('jewelry-and-watches', 'gemstone-jewelry',
                   'https://www.jcpenney.com/g/jewelry-and-watches/gemstone-jewelry?mktTiles=0&id=cat1003050007&cm_re=ZH-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_PersonalizedJewelry_Gemstone_7'),
                  ('jewelry-and-watches', 'children-baby-jewelry',
                   'https://www.jcpenney.com/g/jewelry-and-watches/personalized-jewelry/children-baby-jewelry?mktTiles=0&id=cat1005820004&cm_re=ZH-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_PersonalizedJewelry_ChildrenBaby_8'),
                  ('jewelry-and-watches', 'quinceanera-sweet-16-and-teen-jewelry',
                   'https://www.jcpenney.comhttps://personalizedjewelry.jcpenney.com/shop/category/quinceanera-sweet-16-and-teen-jewelry?cm_re=ZH-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_PersonalizedJewelry_QuinceaneraSweet16Teen_9'),
                  ('jewelry-and-watches', 'personalized-watches',
                   'https://www.jcpenney.com/g/jewelry-and-watches/personalized-jewelry/personalized-watches?mktTiles=0&id=cat1005800005&cm_re=ZH-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_PersonalizedJewelry_PersonalizedWatches_10'),
                  ('jewelry-and-watches', 'fashion-jewelry',
                   'https://www.jcpenney.com/g/jewelry-and-watches/fashion-jewelry?mktTiles=0&id=cat100240091&brand=bijoux+bar&cm_re=ZI-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_Brands_BijouxBar_1'),
                  ('jewelry-and-watches', 'all-watches',
                   'https://www.jcpenney.com/g/jewelry-and-watches/all-watches?mktTiles=0&id=cat100240089&brand=bulova&cm_re=ZI-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_Brands_Bulova_2'),
                  ('jewelry-and-watches', 'all-watches',
                   'https://www.jcpenney.com/g/jewelry-and-watches/all-watches?mktTiles=0&id=cat100240089&brand=citizen%7Ccitizen+quartz%7Cdrive+from+citizen+eco-drive&cm_re=ZI-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_Brands_Citizen_3'),
                  ('jewelry-and-watches', 'jewelry-and-watches',
                   'https://www.jcpenney.com/g/jewelry-and-watches?mktTiles=0&id=dept20000020&jewelry_brand=diamonart&cm_re=ZI-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_Brands_Diamonart_4'),
                  ('jewelry-and-watches', 'effy',
                   'https://www.jcpenney.com/g/jewelry-and-watches/all-fine-jewelry/effy?id=cat11100003643&cm_re=ZI-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-EFFY_5'),
                  ('jewelry-and-watches', 'enchanted-disney-fine-jewelry',
                   'https://www.jcpenney.com/g/jewelry-and-watches/enchanted-disney-fine-jewelry?id=cat1009750001&cm_re=ZI-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_Brands_Disney_6'),
                  ('jewelry-and-watches', 'le-vian-fine-jewelry',
                   'https://www.jcpenney.com/g/jewelry-and-watches/le-vian-fine-jewelry?id=cat11100008053&cm_re=ZI-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_Brands_Levian_7'),
                  ('jewelry-and-watches', 'fashion-jewelry',
                   'https://www.jcpenney.com/g/jewelry-and-watches/fashion-jewelry?brand=liz+claiborne&id=cat100240091&cm_re=ZI-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_Brands_LizClaiborne_8'),
                  ('jewelry-and-watches', 'view-all-modern-bride',
                   'https://www.jcpenney.com/g/jewelry-and-watches/view-all-modern-bride?jewelry_brand=signature+by+modern+bride&id=cat1004860021&cm_re=ZI-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-SIGNATURE-BY-MODERN-BRIDE_9'),
                  ('jewelry-and-watches', 'fashion-jewelry',
                   'https://www.jcpenney.com/g/jewelry-and-watches/fashion-jewelry?mktTiles=0&id=cat100240091&brand=monet+jewelry&cm_re=ZI-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_Brands_Monet_10'),
                  ('jewelry-and-watches', 'all-watches',
                   'https://www.jcpenney.com/g/jewelry-and-watches/all-watches?mktTiles=0&id=cat100240089&brand=samsung&cm_re=ZI-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_Brands_Samsung_11'),
                  ('jewelry-and-watches', 'all-watches',
                   'https://www.jcpenney.com/g/jewelry-and-watches/all-watches?mktTiles=0&id=cat100240089&brand=timex&cm_re=ZI-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_Brands_Timex_12'),
                  ('jewelry-and-watches', 'jewelry-and-watches',
                   'https://www.jcpenney.com/g/jewelry-and-watches?division=005&mktTiles=0&view_all=view+all+brands&id=dept20000020&cm_re=ZI-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_Brands_ViewAllBrands_13'),
                  ('jewelry-and-watches', 'jewelry-education',
                   'https://www.jcpenney.com/m/jewelry-education?cm_re=ZJ-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_HelpfulInformation-1_JewelryEducation_1'),
                  ('jewelry-and-watches', 'jewelry-buying-guides',
                   'https://www.jcpenney.com/m/jewelry-buying-guides?cm_re=ZJ-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_HelpfulInformation-2_JewelryBuyingGuides_2'),
                  ('jewelry-and-watches', 'jewelry-and-watches',
                   'https://www.jtcpenney.com/g/jewelry-and-watches?mktTiles=0&s1_deals_and_promotions=SALE&id=dept20000020&cm_re=ZK-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_SaleClearance_Sale_1'),
                  ('jewelry-and-watches', 'jewelry-and-watches',
                   'https://www.jcpenney.com/g/jewelry-and-watches?mktTiles=0&s1_deals_and_promotions=CLEARANCE&id=dept20000020&cm_re=ZK-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_SaleClearance_Clearance_2'),
                  ('jewelry-and-watches', 'jewelry-and-watches',
                   'https://www.jcpenney.com/g/jewelry-and-watches?division=005&subdivision=237%7C247%7C437%7C447&mktTiles=0&id=dept20000020&cm_re=ZK-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_SaleClearance_LimitedQuantities_3')}
    categories = {('home-store', 'home-store',
                   'https://www.jcpenney.com/g/home-store?new_arrivals=view+all+new&id=dept20000011&cm_re=ZA-_-DEPARTMENT-FOR-THE-HOME-_-LF-_-HOME-DEPARTMENT-PAGE-NEW-ARRIVALS-_-SHOP-ALL-HOME-NEW-ARRIVALS_1'),
                  ('home-store', 'all-bedding',
                   'https://www.jcpenney.com/g/home/bedroom/all-bedding?id=cat100250072&cm_re=ZB-_-DEPARTMENT-FOR-THE-HOME-_-LF-_-DEPARTMENTS-_-BEDDING_1'),
                  ('home-store', 'all-bath',
                   'https://www.jcpenney.com/g/home/all-bath?id=cat100290078&cm_re=ZB-_-DEPARTMENT-FOR-THE-HOME-_-LF-_-DEPARTMENTS-_-BATH_2'),
                  ('home-store', 'kitchen-dining',
                   'https://www.jcpenney.com/d/home-store/kitchen-dining?cm_re=ZB-_-DEPARTMENT-FOR-THE-HOME-_-LF-_-DEPARTMENTS-_-FTH_Departments_KitchenDining_3'),
                  ('home-store', 'window-treatments',
                   'https://www.jcpenney.com/g/home/window-treatments?id=cat100260213&cm_re=ZB-_-DEPARTMENT-FOR-THE-HOME-_-LF-_-DEPARTMENTS-_-FTH_Departments_Window_4'),
                  ('home-store', 'furniture-store',
                   'https://www.jcpenney.com/d/home-store/furniture-store?cm_re=ZB-_-DEPARTMENT-FOR-THE-HOME-_-LF-_-DEPARTMENTS-_-FTH_Departments_Furniture_5'),
                  ('home-store', 'mattresses',
                   'https://www.jcpenney.com/d/mattresses?cm_re=ZB-_-DEPARTMENT-FOR-THE-HOME-_-LF-_-DEPARTMENTS-_-FTH_Departments_Mattresses_6'),
                  ('home-store', 'home-decor',
                   'https://www.jcpenney.com/d/home-store/home-decor?cm_re=ZB-_-DEPARTMENT-FOR-THE-HOME-_-LF-_-DEPARTMENTS-_-FTH_Departments_HomeDecor_7'),
                  ('home-store', 'electronics',
                   'https://www.jcpenney.com/g/home-store/electronics?view_all=view+all+brands&id=cat1008680002&cm_re=ZB-_-DEPARTMENT-FOR-THE-HOME-_-LF-_-DEPARTMENTS-_-ELECTRONICS_8'),
                  ('home-store', 'gifts-for-home',
                   'https://www.jcpenney.com/g/unique-gifts/all-gifts/gifts-for-home?id=cat11100003775&cm_re=ZB-_-DEPARTMENT-FOR-THE-HOME-_-LF-_-DEPARTMENTS-_-GIFTING_9'),
                  ('home-store', 'home-store',
                   'https://www.jcpenney.com/g/home-store?s1_deals_and_promotions=SALE&id=dept20000011&cm_re=ZC-_-DEPARTMENT-FOR-THE-HOME-_-LF-_-FTH_SalesPromotions_Sale_1'),
                  ('home-store', 'home-store',
                   'https://www.jcpenney.com/g/home-store?s1_deals_and_promotions=CLEARANCE&id=dept20000011&cm_re=ZC-_-DEPARTMENT-FOR-THE-HOME-_-LF-_-FTH_SalesPromotions_Clearance_2'),
                  ('home-store', 'rebates',
                   'https://www.jcpenney.com/m/customer-service/rebates?cm_re=ZC-_-DEPARTMENT-FOR-THE-HOME-_-LF-_-FTH_SalesPromotions_RebateCenter_3'),
                  ('home-store', 'storage-organization',
                   'https://www.jcpenney.com/g/home-store/storage-organization?product_type=bins+%2B+baskets&id=cat1002320013&cm_re=ZD-_-DEPARTMENT-FOR-THE-HOME-_-LF-_-FTH_StorageOrganizationCleaning_DECORATIVESTORAGE_1'),
                  ('home-store', 'desktop-office-storage',
                   'https://www.jcpenney.com/g/home-store/storage-organization/desktop-office-storage?id=cat1006100030&cm_re=ZD-_-DEPARTMENT-FOR-THE-HOME-_-LF-_-FTH_StorageOrganizationCleaning_HomeOfficeOrganization_2'),
                  ('home-store', 'storage-furniture',
                   'https://www.jcpenney.com/g/home-store/storage-organization/storage-furniture?id=cat100440010&cm_re=ZD-_-DEPARTMENT-FOR-THE-HOME-_-LF-_-FTH_StorageOrganizationCleaning_StorageFurniture_3'),
                  ('home-store', 'irons-laundry-care',
                   'https://www.jcpenney.com/g/home-store/irons-laundry-care?id=cat100440007&cm_re=ZD-_-DEPARTMENT-FOR-THE-HOME-_-LF-_-FTH_StorageOrganizationCleaning_IronsLaundry_4'),
                  ('home-store', 'vacuums-floorcare',
                   'https://www.jcpenney.com/g/home-store/vacuums-floorcare?id=cat100250081&cm_re=ZD-_-DEPARTMENT-FOR-THE-HOME-_-LF-_-FTH_StorageOrganizationCleaning_VacuumsFloorCare_5'),
                  ('home-store', 'storage-organization',
                   'https://www.jcpenney.com/g/home-store/storage-organization?id=cat1002320013&cm_re=ZD-_-DEPARTMENT-FOR-THE-HOME-_-LF-_-FTH_StorageOrganizationCleaning_ViewAllStorageOrganization_6'),
                  ('home-store', 'fans-air-purifiers',
                   'https://www.jcpenney.com/g/home-store/fans-air-purifiers?id=cat100440005&cm_re=ZE-_-DEPARTMENT-FOR-THE-HOME-_-LF-_-FTH_FeaturedCategories_FansandAir_1'),
                  ('home-store', 'pet-care',
                   'https://www.jcpenney.com/g/home-store/pet-care?id=cat100210004&cm_re=ZE-_-DEPARTMENT-FOR-THE-HOME-_-LF-_-FTH_FeaturedCategories_PetCare_2'),
                  ('home-store', 'home-store',
                   'https://www.jcpenney.com/g/home-store?features=antimicrobial&id=dept20000011&cm_re=ZE-_-DEPARTMENT-FOR-THE-HOME-_-LF-_-FTH_FeaturedCategories_Antimicrobial_3'),
                  ('home-store', 'home-store',
                   'https://www.jcpenney.com/g/home-store?marketing_theme=healthy+sleep&id=dept20000011&cm_re=ZE-_-DEPARTMENT-FOR-THE-HOME-_-LF-_-FTH_FeaturedCategories_HealthySleep_4'),
                  ('home-store', 'kitchen-dining',
                   'https://www.jcpenney.com/g/home-store/kitchen-dining?marketing_theme=wellness&id=cat100240016&cm_re=ZE-_-DEPARTMENT-FOR-THE-HOME-_-LF-_-FTH_FeaturedCategories_HealthyEating_5'),
                  ('home-store', 'luggage',
                   'https://www.jcpenney.com/g/home-store/luggage?id=cat100210003&cm_re=ZE-_-DEPARTMENT-FOR-THE-HOME-_-LF-_-FTH_FeaturedCategories_Travel_Luggage_6'),
                  ('home-store', 'backpacks-messenger-bags',
                   'https://www.jcpenney.com/g/home-store/backpacks-messenger-bags?id=cat100300083&cm_re=ZE-_-DEPARTMENT-FOR-THE-HOME-_-LF-_-FTH_FeaturedCategories_Backpack_Duffel_7'),
                  ('home-store', 'home-store',
                   'https://www.jcpenney.com/g/home-store?features=as+seen+on+tv&id=dept20000011&cm_re=ZE-_-DEPARTMENT-FOR-THE-HOME-_-LF-_-FTH_FeaturedCategories_ASOTV_8'),
                  ('home-store', 'home-store',
                   'https://www.jcpenney.com/g/home-store?marketing_theme=work+from+home&id=dept20000011&cm_re=ZE-_-DEPARTMENT-FOR-THE-HOME-_-LF-_-HOME-OFFICE_9'),
                  ('home-store', 'furniture',
                   'https://www.jcpenney.com/g/home-store/patio-outdoor-living/furniture?id=cat100240095&cm_re=ZF-_-DEPARTMENT-FOR-THE-HOME-_-LF-_-PATIO-FURNITURE_1'),
                  ('home-store', 'outdoor-rugs-doormats',
                   'https://www.jcpenney.com/g/home-store/patio-outdoor-living/outdoor-rugs-doormats?id=cat100260273&cm_re=ZF-_-DEPARTMENT-FOR-THE-HOME-_-LF-_-OUTDOOR-RUGS_2'),
                  ('home-store', 'outdoor-decor',
                   'https://www.jcpenney.com/g/home-store/patio-outdoor-living/outdoor-decor?id=cat100260272&cm_re=ZF-_-DEPARTMENT-FOR-THE-HOME-_-LF-_-FTH_Patio_OutdoorDecor_3'),
                  ('home-store', 'outdoor-dining',
                   'https://www.jcpenney.com/g/home-store/patio-furniture-sets/outdoor-dining?id=cat100310037&cm_re=ZF-_-DEPARTMENT-FOR-THE-HOME-_-LF-_-FTH_Patio_Outdoordining_4'),
                  ('home-store', 'patio-outdoor-living',
                   'https://www.jcpenney.com/g/home-store/patio-outdoor-living?id=cat100210002&cm_re=ZF-_-DEPARTMENT-FOR-THE-HOME-_-LF-_-FTH_Patio_ViewAllPatio_5'),
                  ('home-store', 'camping-outdoor',
                   'https://www.jcpenney.com/g/home-store/camping-outdoor?id=cat1005540005&cm_re=ZG-_-DEPARTMENT-FOR-THE-HOME-_-LF-_-FTH_SportsOutdoors_CampingOutdoor_1'),
                  ('home-store', 'outdoor-toys-and-games',
                   'https://www.jcpenney.com/g/toys-and-games/all-toys-and-games/outdoor-toys-and-games?id=cat11100001526&cm_re=ZG-_-DEPARTMENT-FOR-THE-HOME-_-LF-_-FTH_SportsOutdoors_Games_2'),
                  ('home-store', 'd-19448832+z-9343195-1363098801',
                   'https://www.jcpenney.comhttps://sportsfanshop.jcpenney.com/home-and-office/d-19448832+z-9343195-1363098801?_s=bm-JCP-DT-Dept-Home-left-nav&cm_re=ZG-_-DEPARTMENT-FOR-THE-HOME-_-LF-_-FTH_SportsOutdoors_SFS_3'),
                  ('home-store', 'home-store',
                   'https://www.jcpenney.com/g/home-store?brand=broadhaven&id=dept20000011&boostIds=ppr5008391587&cm_re=ZH-_-DEPARTMENT-FOR-THE-HOME-_-LF-_-BROADHAVEN_1'),
                  ('home-store', 'cooks',
                   'https://www.jcpenney.com/g/home-store/kitchen-dining/cooks?id=cat11100007010&cm_re=ZH-_-DEPARTMENT-FOR-THE-HOME-_-LF-_-FTH_Brands_Cooks_2'),
                  ('home-store', 'distant-lands',
                   'https://www.jcpenney.com/g/home-store/distant-lands?id=cat11100007443&cm_re=ZH-_-DEPARTMENT-FOR-THE-HOME-_-LF-_-DISTANT-LANDS_3'),
                  ('home-store', 'fieldcrest',
                   'https://www.jcpenney.com/g/home-store/fieldcrest?id=cat11100000795&cm_re=ZH-_-DEPARTMENT-FOR-THE-HOME-_-LF-_-FIELDCREST_4'),
                  ('home-store', 'home-store',
                   'https://www.jcpenney.com/g/home-store?brand=frye+and+co&id=dept20000011&cm_re=ZH-_-DEPARTMENT-FOR-THE-HOME-_-LF-_-FRYE-CO_5'),
                  ('home-store', 'home-expressions',
                   'https://www.jcpenney.com/g/home-store/home-expressions?id=cat11100003849&cm_re=ZH-_-DEPARTMENT-FOR-THE-HOME-_-LF-_-FTH_Brands_HomeExpressions_6'),
                  ('home-store', 'home-store',
                   'https://www.jcpenney.com/g/home-store?brand=izod&id=dept20000011&cm_re=ZH-_-DEPARTMENT-FOR-THE-HOME-_-LF-_-IZOD_7'),
                  ('home-store', 'linden-street',
                   'https://www.jcpenney.com/g/home-store/linden-street?id=cat10010830002&cm_re=ZH-_-DEPARTMENT-FOR-THE-HOME-_-LF-_-FTH_Brands_LindenStreet_8'),
                  ('home-store', 'home-store',
                   'https://www.jcpenney.com/g/home-store?brand=liz+claiborne&id=dept20000011&cm_re=ZH-_-DEPARTMENT-FOR-THE-HOME-_-LF-_-FTH_Brands_LizClaiborne_9'),
                  ('home-store', 'loom-and-forge',
                   'https://www.jcpenney.com/g/home-store/loom-and-forge?id=cat11100001877&cm_re=ZH-_-DEPARTMENT-FOR-THE-HOME-_-LF-_-LOOM-FORGE_10'),
                  ('home-store', 'home-store',
                   'https://www.jcpenney.com/g/home-store?brand=madison+park%7Cmadison+park+essentials%7Cmadison+park+signature&id=dept20000011&cm_re=ZH-_-DEPARTMENT-FOR-THE-HOME-_-LF-_-MADISON-PARK_11'),
                  ('home-store', 'home-store',
                   'https://www.jcpenney.com/g/home-store?brand=martha+stewart&id=dept20000011&cm_re=ZH-_-DEPARTMENT-FOR-THE-HOME-_-LF-_-MARTHA-STEWART_12'),
                  ('home-store', 'home-store',
                   'https://www.jcpenney.com/g/home-store?brand=samsonite&id=dept20000011&cm_re=ZH-_-DEPARTMENT-FOR-THE-HOME-_-LF-_-FTH_Brands_Samsonite_13'),
                  ('home-store', 'view-all-mattresses',
                   'https://www.jcpenney.com/g/mattresses/view-all-mattresses?brand=sealy&id=cat1009550014&cm_re=ZH-_-DEPARTMENT-FOR-THE-HOME-_-LF-_-FTH_Brands_Sealy_14'),
                  ('home-store', 'view-all-mattresses',
                   'https://www.jcpenney.com/g/mattresses/view-all-mattresses?brand=serta&id=cat1009550014&cm_re=ZH-_-DEPARTMENT-FOR-THE-HOME-_-LF-_-FTH_Brands_Serta_15'),
                  ('home-store', 'sharper-image',
                   'https://www.jcpenney.com/g/home-store/sharper-image?id=cat10010400002&cm_re=ZH-_-DEPARTMENT-FOR-THE-HOME-_-LF-_-FTH_Brands_SharperImage_16'),
                  ('home-store', 'home-store',
                   'https://www.jcpenney.com/g/home-store?brand=signature+design+by+ashley&id=dept20000011&cm_re=ZH-_-DEPARTMENT-FOR-THE-HOME-_-LF-_-FTH_Brands_Ashley_17'),
                  ('home-store', 'home-store',
                   'https://www.jcpenney.com/g/home-store?view_all=view+all+brands&id=dept20000011&cm_re=ZH-_-DEPARTMENT-FOR-THE-HOME-_-LF-_-FTH_Brands_ViewAllBrands_18')}
    categories = {('young-adult', 'juniors',
                   'https://www.jcpenney.com/g/juniors?new_arrivals=view+all+new&size_range=juniors+plus+size%7Cjuniors+size&id=dept20023450025&cm_re=ZA-_-DEPARTMENT-YOUNG-ADULT-_-LF-_-VIEW-ALL-JUNIORS-NEW-ARRIVALS_1'),
                  ('young-adult', 'view-all-guys',
                   'https://www.jcpenney.com/g/men/view-all-guys?id=cat100250145&sort=NA&cm_re=ZA-_-DEPARTMENT-YOUNG-ADULT-_-LF-_-VIEW-ALL-YOUNG-MENS-NEW-ARRIVALS_2'),
                  ('young-adult', 'juniors-tops',
                   'https://www.jcpenney.com/g/juniors/juniors-tops?id=cat100240014&cm_re=ZB-_-DEPARTMENT-YOUNG-ADULT-_-LF-_-TOPS_1'),
                  ('young-adult', 'jeans',
                   'https://www.jcpenney.com/g/juniors/jeans?id=cat100250132&cm_re=ZB-_-DEPARTMENT-YOUNG-ADULT-_-LF-_-JEANS_2'),
                  ('young-adult', 'juniors-graphic-tees',
                   'https://www.jcpenney.com/g/juniors/juniors-graphic-tees?id=cat100250156&cm_re=ZB-_-DEPARTMENT-YOUNG-ADULT-_-LF-_-GRAPHIC-TEES_3'),
                  ('young-adult', 'juniors-hoodies',
                   'https://www.jcpenney.com/g/juniors/juniors-hoodies?id=cat1004700049&cm_re=ZB-_-DEPARTMENT-YOUNG-ADULT-_-LF-_-HOODIES-SWEATSHIRTS_4'),
                  ('young-adult', 'juniors-school-uniforms',
                   'https://www.jcpenney.com/g/juniors/juniors-school-uniforms?id=cat100250160&cm_re=ZB-_-DEPARTMENT-YOUNG-ADULT-_-LF-_-UNIFORMS_5'),
                  ('young-adult', 'dresses',
                   'https://www.jcpenney.com/g/juniors/dresses?id=cat100240012&cm_re=ZB-_-DEPARTMENT-YOUNG-ADULT-_-LF-_-DRESSES_6'),
                  ('young-adult', 'juniors-skirts',
                   'https://www.jcpenney.com/g/juniors/juniors-skirts?id=cat100630341&cm_re=ZB-_-DEPARTMENT-YOUNG-ADULT-_-LF-_-SKIRTS_7'),
                  ('young-adult', 'juniors-workout-clothes',
                   'https://www.jcpenney.com/g/juniors/juniors-workout-clothes?id=cat100250134&cm_re=ZB-_-DEPARTMENT-YOUNG-ADULT-_-LF-_-ACTIVEWEAR_8'),
                  ('young-adult', 'juniors-jackets-coats',
                   'https://www.jcpenney.com/g/juniors/juniors-jackets-coats?id=cat100240013&cm_re=ZB-_-DEPARTMENT-YOUNG-ADULT-_-LF-_-COATS-JACKETS_9'),
                  ('young-adult', 'juniors-bras-panties-sleepwear',
                   'https://www.jcpenney.com/g/juniors/juniors-bras-panties-sleepwear?id=cat11100007836&cm_re=ZB-_-DEPARTMENT-YOUNG-ADULT-_-LF-_-BRAS-PANTIES-PAJAMAS_10'),
                  ('young-adult', 'young-mens-shirts',
                   'https://www.jcpenney.com/g/men/view-all-guys/young-mens-shirts?id=cat11100000100&cm_re=ZC-_-DEPARTMENT-YOUNG-ADULT-_-LF-_-SHIRTS_1'),
                  ('young-adult', 'mens-graphic-tees',
                   'https://www.jcpenney.com/g/men/mens-graphic-tees?id=cat1002990005&cm_re=ZC-_-DEPARTMENT-YOUNG-ADULT-_-LF-_-GRAPHIC-TEES_2'),
                  ('young-adult', 'young-mens-shorts',
                   'https://www.jcpenney.com/g/men/view-all-guys/young-mens-shorts?id=cat11100000103&cm_re=ZC-_-DEPARTMENT-YOUNG-ADULT-_-LF-_-SHORTS_3'),
                  ('young-adult', 'young-mens-jeans',
                   'https://www.jcpenney.com/g/men/view-all-guys/young-mens-jeans?id=cat11100000102&cm_re=ZC-_-DEPARTMENT-YOUNG-ADULT-_-LF-_-JEANS_4'),
                  ('young-adult', 'young-mens-pants',
                   'https://www.jcpenney.com/g/men/view-all-guys/young-mens-pants?id=cat11100000104&cm_re=ZC-_-DEPARTMENT-YOUNG-ADULT-_-LF-_-PANTS_5'),
                  ('young-adult', 'young-mens-uniforms',
                   'https://www.jcpenney.com/g/men/view-all-guys/young-mens-uniforms?id=cat11100000113&cm_re=ZC-_-DEPARTMENT-YOUNG-ADULT-_-LF-_-SCHOOL-UNIFORMS_6'),
                  ('young-adult', 'young-mens-hoodies-sweatshirts',
                   'https://www.jcpenney.com/g/men/view-all-guys/young-mens-hoodies-sweatshirts?id=cat11100000105&cm_re=ZC-_-DEPARTMENT-YOUNG-ADULT-_-LF-_-HOODIES-SWEATSHIRTS_7'),
                  ('young-adult', 'view-all-guys',
                   'https://www.jcpenney.com/g/men/view-all-guys?product_type=coats+%2B+jackets&id=cat100250145&cm_re=ZC-_-DEPARTMENT-YOUNG-ADULT-_-LF-_-JACKETS_8'),
                  ('young-adult', 'men',
                   'https://www.jcpenney.com/g/men?brand=jf+j.ferrar&gender=mens&product_type=sport+coats%7Csuit+bottoms%7Csuit+jackets&id=dept20000014&cm_re=ZC-_-DEPARTMENT-YOUNG-ADULT-_-LF-_-DRESS-CLOTHES_9'),
                  ('young-adult', 'young-mens-activewear',
                   'https://www.jcpenney.com/g/men/view-all-guys/young-mens-activewear?id=cat11100000101&cm_re=ZC-_-DEPARTMENT-YOUNG-ADULT-_-LF-_-ACTIVEWEAR_10'),
                  ('young-adult', 'brand',
                   'https://www.jcpenney.com/g/brand?brand=airwalk&cm_re=ZD-_-DEPARTMENT-YOUNG-ADULT-_-LF-_-AIRWALK_1'),
                  ('young-adult', 'juniors',
                   'https://www.jcpenney.com/g/juniors?brand=arizona&id=dept20023450025&cm_re=ZD-_-DEPARTMENT-YOUNG-ADULT-_-LF-_-ARIZONA_2'),
                  ('young-adult', 'arizona-body',
                   'https://www.jcpenney.com/g/juniors/arizona-body?id=cat11100007699&cm_re=ZD-_-DEPARTMENT-YOUNG-ADULT-_-LF-_-ARIZONA-BODY_3'),
                  ('young-adult', 'by-by',
                   'https://www.jcpenney.com/g/juniors/by-by?id=cat11100008502&cm_re=ZD-_-DEPARTMENT-YOUNG-ADULT-_-LF-_-BY-BY_4'),
                  ('young-adult', 'champion',
                   'https://www.jcpenney.com/g/shops/champion?id=cat1009340015&cm_re=ZD-_-DEPARTMENT-YOUNG-ADULT-_-LF-_-CHAMPION_5'),
                  ('young-adult', 'forever-21',
                   'https://www.jcpenney.com/g/shops/all-brands/forever-21?id=cat11100020270&cm_re=ZD-_-DEPARTMENT-YOUNG-ADULT-_-LF-_-FOREVER-21_6'),
                  ('young-adult', 'juicy-by-juicy-couture',
                   'https://www.jcpenney.com/g/women/juicy-by-juicy-couture?id=cat11100004760&cm_re=ZD-_-DEPARTMENT-YOUNG-ADULT-_-LF-_-JUICY-BY-JUICY-COUTURE_7'),
                  ('young-adult', 'levis',
                   'https://www.jcpenney.com/g/shops/levis?id=cat1009340019&cm_re=ZD-_-DEPARTMENT-YOUNG-ADULT-_-LF-_-LEVIS_8'),
                  ('young-adult', 'young-adult-formal-apparel-and-accessories',
                   'https://www.jcpenney.com/g/shops/young-adult-formal-apparel-and-accessories?id=cat11100017436&cm_re=ZE-_-DEPARTMENT-YOUNG-ADULT-_-LF-_-HOMECOMING-SHOP_1'),
                  ('young-adult', 'young-adult-beauty',
                   'https://www.jcpenney.com/g/beauty/young-adult-beauty?id=cat11100007563&cm_re=ZE-_-DEPARTMENT-YOUNG-ADULT-_-LF-_-BEAUTY_2'),
                  ('young-adult', 'ga-36+z-9787150860-494237232',
                   'https://www.jcpenney.comhttps://sportsfanshop.jcpenney.com/kids/ga-36+z-9787150860-494237232?cm_re=ZE-_-DEPARTMENT-YOUNG-ADULT-_-LF-_-SPORTS-FAN-SHOP_3'),
                  ('young-adult', 'juniors-accessories',
                   'https://www.jcpenney.com/g/juniors/juniors-accessories?id=cat1009220001&cm_re=ZF-_-DEPARTMENT-YOUNG-ADULT-_-LF-_-JUNIORS-ACCESSORIES_1'),
                  ('young-adult', 'juniors-shoes',
                   'https://www.jcpenney.com/g/juniors/juniors-shoes?id=cat1007420004&cm_re=ZF-_-DEPARTMENT-YOUNG-ADULT-_-LF-_-JUNIORS-SHOES_2'),
                  ('young-adult', 'juniors-accessories',
                   'https://www.jcpenney.com/g/juniors/juniors-accessories?product_type=bags+%2B+backpacks%7Chandbags&id=cat1009220001&cm_re=ZF-_-DEPARTMENT-YOUNG-ADULT-_-LF-_-HANDBAGS_3'),
                  ('young-adult', 'socks-hosiery-and-tights',
                   'https://www.jcpenney.com/g/purses-accessories/socks-hosiery-and-tights?id=cat100640310&cm_re=ZF-_-DEPARTMENT-YOUNG-ADULT-_-LF-_-SOCKS-HOSIERY-TIGHTS_4'),
                  ('young-adult', 'view-all-guys',
                   'https://www.jcpenney.com/g/men/view-all-guys?product_type=shoes&id=cat100250145&cm_re=ZF-_-DEPARTMENT-YOUNG-ADULT-_-LF-_-YOUNG-MENS-SHOES_5'),
                  ('young-adult', 'underwear-socks',
                   'https://www.jcpenney.com/g/men/underwear-socks?age_group=young+mens&id=cat11100000472&cm_re=ZF-_-DEPARTMENT-YOUNG-ADULT-_-LF-_-YOUNG-MENS-SOCKS-UNDERWEAR_6'),
                  ('young-adult', 'juniors',
                   'https://www.jcpenney.com/g/juniors?s1_deals_and_promotions=SALE&size_range=juniors+plus+size%7Cjuniors+size&id=dept20023450025&cm_re=ZG-_-DEPARTMENT-YOUNG-ADULT-_-LF-_-JUNIORS-SALE_1'),
                  ('young-adult', 'juniors',
                   'https://www.jcpenney.com/g/juniors?s1_deals_and_promotions=CLEARANCE&id=dept20023450025&cm_re=ZG-_-DEPARTMENT-YOUNG-ADULT-_-LF-_-JUNIORS-CLEARANCE_2'),
                  ('young-adult', 'view-all-guys',
                   'https://www.jcpenney.com/g/men/view-all-guys?s1_deals_and_promotions=SALE&id=cat100250145&cm_re=ZG-_-DEPARTMENT-YOUNG-ADULT-_-LF-_-YOUNG-MENS-SALE_3'),
                  ('young-adult', 'view-all-guys',
                   'https://www.jcpenney.com/g/men/view-all-guys?s1_deals_and_promotions=CLEARANCE&id=cat100250145&cm_re=ZG-_-DEPARTMENT-YOUNG-ADULT-_-LF-_-YOUNG-MENS-CLEARANCE_4')}
    categories = {('baby-kids', 'baby-kids',
                   'https://www.jcpenney.com/g/baby-kids?new_arrivals=view+all+new&id=dept11100000014&cm_re=ZA-_-DEPARTMENT-BABY-KIDS-_-LF-_-VIEW-ALL-BABY-KIDS-NEW-ARRIVALS_1'),
                  ('baby-kids', 'baby-boy-clothes-0-24-months',
                   'https://www.jcpenney.com/g/baby/baby-boy-clothes-0-24-months?id=cat100260040&cm_re=ZB-_-DEPARTMENT-BABY-KIDS-_-LF-_-BOYS-_-Boys-BABY-BOY-0-24-MONTHS_1'),
                  ('baby-kids', 'boys-2t-5t-toddler-clothing',
                   'https://www.jcpenney.com/g/baby-kids/all-boys-clothing/boys-2t-5t-toddler-clothing?id=cat11100001197&cm_re=ZB-_-DEPARTMENT-BABY-KIDS-_-LF-_-BOYS-_-BOYS-TODDLER-12-M-5-T_2'),
                  ('baby-kids', 'little-boys-4-7-clothing',
                   'https://www.jcpenney.com/g/baby-kids/all-boys-clothing/little-boys-4-7-clothing?id=cat11100001198&cm_re=ZB-_-DEPARTMENT-BABY-KIDS-_-LF-_-BOYS-_-Boys-LITTLE-BOYS-4-7_3'),
                  ('baby-kids', 'big-boys-8-20-clothing',
                   'https://www.jcpenney.com/g/baby-kids/all-boys-clothing/big-boys-8-20-clothing?id=cat11100001199&cm_re=ZB-_-DEPARTMENT-BABY-KIDS-_-LF-_-BOYS-_-Boys-BIG-KID-8-22_4'),
                  ('baby-kids', 'kids-husky',
                   'https://www.jcpenney.com/g/baby-kids/kids/kids-husky?id=cat11100000028&cm_re=ZB-_-DEPARTMENT-BABY-KIDS-_-LF-_-BOYS-_-Boys-Husky_5'),
                  ('baby-kids', 'boys-adaptive-clothing-accessories',
                   'https://www.jcpenney.com/g/baby-kids/all-boys-clothing/boys-adaptive-clothing-accessories?id=cat11100007073&cm_re=ZB-_-DEPARTMENT-BABY-KIDS-_-LF-_-BOYS-_-Boys-ADAPTIVE-CLOTHING_6'),
                  ('baby-kids', 'all-boys-clothing',
                   'https://www.jcpenney.com/g/baby-kids/all-boys-clothing?id=cat11100001196&cm_re=ZB-_-DEPARTMENT-BABY-KIDS-_-LF-_-BOYS-_-Boys-SHOP-ALL-BOYS_7'),
                  ('baby-kids', 'boys',
                   'https://www.jcpenney.com/g/baby-kids/all-bottoms/shorts/boys?id=cat11100000042&cm_re=ZB-_-DEPARTMENT-BABY-KIDS-_-LF-_-BOYS-_-SHORTS_8'),
                  ('baby-kids', 'boys',
                   'https://www.jcpenney.com/g/baby-kids/swimwear/boys?id=cat11100000071&cm_re=ZB-_-DEPARTMENT-BABY-KIDS-_-LF-_-BOYS-_-SWIMWEAR_9'),
                  ('baby-kids', 'boys',
                   'https://www.jcpenney.com/g/baby-kids/all-tops/shirts-tops/boys?id=cat11100000020&cm_re=ZB-_-DEPARTMENT-BABY-KIDS-_-LF-_-BOYS-_-Boys-SHIRTS-AMP-TEES_10'),
                  ('baby-kids', 'kids-suits-and-dress-clothes',
                   'https://www.jcpenney.com/g/baby-kids/kids-suits-and-dress-clothes?id=cat11100000063&cm_re=ZB-_-DEPARTMENT-BABY-KIDS-_-LF-_-BOYS-_-Boys-SUITS-AMP-DRESS-CLOTHES_11'),
                  ('baby-kids', 'boys',
                   'https://www.jcpenney.com/g/baby-kids/all-bottoms/jeans/boys?id=cat11100000036&cm_re=ZB-_-DEPARTMENT-BABY-KIDS-_-LF-_-BOYS-_-Boys-JEANS_12'),
                  ('baby-kids', 'boys',
                   'https://www.jcpenney.com/g/baby-kids/clothing-sets/boys?id=cat11100000054&cm_re=ZB-_-DEPARTMENT-BABY-KIDS-_-LF-_-BOYS-_-Boys-SETS-AMP-OUTFITS_13'),
                  ('baby-kids', 'boys',
                   'https://www.jcpenney.com/g/baby-kids/activewear/boys?id=cat11100000083&cm_re=ZB-_-DEPARTMENT-BABY-KIDS-_-LF-_-BOYS-_-Boys-ACTIVEWEAR_14'),
                  ('baby-kids', 'boys',
                   'https://www.jcpenney.com/g/baby-kids/all-bottoms/pants/boys?id=cat11100000039&cm_re=ZB-_-DEPARTMENT-BABY-KIDS-_-LF-_-BOYS-_-Boys-PANTS-JOGGERS_15'),
                  ('baby-kids', 'boys',
                   'https://www.jcpenney.com/g/baby-kids/kids-all-tops/hoodies-sweatshirts/boys?id=cat11100000048&cm_re=ZB-_-DEPARTMENT-BABY-KIDS-_-LF-_-BOYS-_-Boys-HOODIES-AMP-SWEATSHIRTS_16'),
                  ('baby-kids', 'boys',
                   'https://www.jcpenney.com/g/baby-kids/outerwear/coats-jackets/boys?id=cat11100000068&cm_re=ZB-_-DEPARTMENT-BABY-KIDS-_-LF-_-BOYS-_-JACKETS_17'),
                  ('baby-kids', 'boys',
                   'https://www.jcpenney.com/g/baby-kids/pajamas-robes/boys?id=cat11100000057&cm_re=ZB-_-DEPARTMENT-BABY-KIDS-_-LF-_-BOYS-_-Boys-PAJAMAS-AMP-ROBES_18'),
                  ('baby-kids', 'boys',
                   'https://www.jcpenney.com/g/baby-kids/underwear-socks/boys?id=cat11100000051&cm_re=ZB-_-DEPARTMENT-BABY-KIDS-_-LF-_-BOYS-_-Boys-UNDERWEAR-AMP-SOCKS_19'),
                  ('baby-kids', 'boys-shoes',
                   'https://www.jcpenney.com/g/shoes/boys-shoes?id=cat100250180&cm_re=ZB-_-DEPARTMENT-BABY-KIDS-_-LF-_-BOYS-_-Boys-Shoes_20'),
                  ('baby-kids', 'accessories',
                   'https://www.jcpenney.com/g/baby-kids/accessories?gender=boys%7Cunisex+kids&id=cat11100000061&cm_re=ZB-_-DEPARTMENT-BABY-KIDS-_-LF-_-BOYS-_-Boys-Accessories_21'),
                  ('baby-kids', 'backpacks-messenger-bags',
                   'https://www.jcpenney.com/g/home-store/backpacks-messenger-bags?gender=boys%7Cunisex+kids&id=cat100300083&boostIds=ppr5008136097-ppr5008136081-ppr5008363062-ppr5008359344-ppr5008368538-ppr5008368539-ppr5007823153-ppr5008363069&cm_re=ZB-_-DEPARTMENT-BABY-KIDS-_-LF-_-BOYS-_-BOYS-BACKPACKS_22'),
                  ('baby-kids', 'baby-girl-clothes-0-24-months',
                   'https://www.jcpenney.com/g/baby/baby-girl-clothes-0-24-months?id=cat100260041&cm_re=ZC-_-DEPARTMENT-BABY-KIDS-_-LF-_-GIRLS-_-Girls-BABY-GIRL-0-24-MONTHS_1'),
                  ('baby-kids', 'girls-2t-5t-toddler-clothing',
                   'https://www.jcpenney.com/g/baby-kids/all-girls-clothing/girls-2t-5t-toddler-clothing?id=cat11100001193&cm_re=ZC-_-DEPARTMENT-BABY-KIDS-_-LF-_-GIRLS-_-GIRLS-TODDLER-12-M-5-T_2'),
                  ('baby-kids', 'little-girls-4-6x-clothing',
                   'https://www.jcpenney.com/g/baby-kids/all-girls-clothing/little-girls-4-6x-clothing?id=cat11100001194&cm_re=ZC-_-DEPARTMENT-BABY-KIDS-_-LF-_-GIRLS-_-Girls-LITTLE-GIRLS-4-7_3'),
                  ('baby-kids', 'big-girls-7-16-clothing',
                   'https://www.jcpenney.com/g/baby-kids/all-girls-clothing/big-girls-7-16-clothing?id=cat11100001195&cm_re=ZC-_-DEPARTMENT-BABY-KIDS-_-LF-_-GIRLS-_-Girls-BIG-KID-7-16_4'),
                  ('baby-kids', 'kids-plus',
                   'https://www.jcpenney.com/g/baby-kids/kids/kids-plus?id=cat11100000027&cm_re=ZC-_-DEPARTMENT-BABY-KIDS-_-LF-_-GIRLS-_-Girls-PLUS_5'),
                  ('baby-kids', 'girls-adaptive-clothing-accessories',
                   'https://www.jcpenney.com/g/baby-kids/all-girls-clothing/girls-adaptive-clothing-accessories?id=cat11100007072&cm_re=ZC-_-DEPARTMENT-BABY-KIDS-_-LF-_-GIRLS-_-Girls-ADAPTIVE-CLOTHING_6'),
                  ('baby-kids', 'all-girls-clothing',
                   'https://www.jcpenney.com/g/baby-kids/all-girls-clothing?id=cat11100001191&cm_re=ZC-_-DEPARTMENT-BABY-KIDS-_-LF-_-GIRLS-_-Girls-AllGirls_7'),
                  ('baby-kids', 'girls',
                   'https://www.jcpenney.com/g/baby-kids/all-bottoms/shorts/girls?id=cat11100000041&cm_re=ZC-_-DEPARTMENT-BABY-KIDS-_-LF-_-GIRLS-_-SHORTS_8'),
                  ('baby-kids', 'girls',
                   'https://www.jcpenney.com/g/baby-kids/swimwear/girls?id=cat11100000070&cm_re=ZC-_-DEPARTMENT-BABY-KIDS-_-LF-_-GIRLS-_-SWIMWEAR_9'),
                  ('baby-kids', 'girls',
                   'https://www.jcpenney.com/g/baby-kids/all-tops/shirts-tops/girls?id=cat11100000032&cm_re=ZC-_-DEPARTMENT-BABY-KIDS-_-LF-_-GIRLS-_-Girls-SHIRTS-AMP-TOPS_10'),
                  ('baby-kids', 'dresses-jumpsuits',
                   'https://www.jcpenney.com/g/baby-kids/dresses-jumpsuits?id=cat11100000098&cm_re=ZC-_-DEPARTMENT-BABY-KIDS-_-LF-_-GIRLS-_-Girls-DRESSES-AMP-JUMPSUITS_11'),
                  ('baby-kids', 'girls',
                   'https://www.jcpenney.com/g/baby-kids/all-bottoms/jeans/girls?id=cat11100000035&cm_re=ZC-_-DEPARTMENT-BABY-KIDS-_-LF-_-GIRLS-_-Girls-JEANS-JEGGINGS_12'),
                  ('baby-kids', 'girls',
                   'https://www.jcpenney.com/g/baby-kids/clothing-sets/girls?id=cat11100000053&cm_re=ZC-_-DEPARTMENT-BABY-KIDS-_-LF-_-GIRLS-_-Girls-SETS-AMP-OUTFITS_13'),
                  ('baby-kids', 'girls',
                   'https://www.jcpenney.com/g/baby-kids/activewear/girls?id=cat11100000082&cm_re=ZC-_-DEPARTMENT-BABY-KIDS-_-LF-_-GIRLS-_-Girls-Activewear_14'),
                  ('baby-kids', 'girls',
                   'https://www.jcpenney.com/g/baby-kids/all-bottoms/pants/girls?id=cat11100000038&cm_re=ZC-_-DEPARTMENT-BABY-KIDS-_-LF-_-GIRLS-_-Girls-PANTS-LEGGINGS_15'),
                  ('baby-kids', 'girls',
                   'https://www.jcpenney.com/g/baby-kids/all-tops/hoodies-sweatshirts/girls?id=cat11100000046&cm_re=ZC-_-DEPARTMENT-BABY-KIDS-_-LF-_-GIRLS-_-Girls-HOODIES-AMP-SWEATSHIRTS_16'),
                  ('baby-kids', 'girls',
                   'https://www.jcpenney.com/g/baby-kids/outerwear/coats-jackets/girls?id=cat11100000067&cm_re=ZC-_-DEPARTMENT-BABY-KIDS-_-LF-_-GIRLS-_-JACKETS_17'),
                  ('baby-kids', 'girls',
                   'https://www.jcpenney.com/g/baby-kids/pajamas-robes/girls?id=cat11100000056&cm_re=ZC-_-DEPARTMENT-BABY-KIDS-_-LF-_-GIRLS-_-Girls-PAJAMAS-AMP-ROBES_18'),
                  ('baby-kids', 'girls',
                   'https://www.jcpenney.com/g/baby-kids/underwear-socks/girls?id=cat11100000050&cm_re=ZC-_-DEPARTMENT-BABY-KIDS-_-LF-_-GIRLS-_-Girls-UNDERWEAR-BRAS-AMP-SOCKS_19'),
                  ('baby-kids', 'girls-shoes',
                   'https://www.jcpenney.com/g/shoes/girls-shoes?id=cat100250179&cm_re=ZC-_-DEPARTMENT-BABY-KIDS-_-LF-_-GIRLS-_-Girls-Shoes_20'),
                  ('baby-kids', 'accessories',
                   'https://www.jcpenney.com/g/baby-kids/accessories?gender=girls%7Cunisex+kids&id=cat11100000061&cm_re=ZC-_-DEPARTMENT-BABY-KIDS-_-LF-_-GIRLS-_-ACCESSORIES_21'),
                  ('baby-kids', 'backpacks-messenger-bags',
                   'https://www.jcpenney.com/g/home-store/backpacks-messenger-bags?gender=girls%7Cunisex+kids&id=cat100300083&boostIds=ppr5008136081-ppr5008327024-ppr5008368540-ppr5008139086-ppr5008206484-ppr5008193732-ppr5008319907-ppr5007823153-ppr5008363067-ppr5008193732&cm_re=ZC-_-DEPARTMENT-BABY-KIDS-_-LF-_-GIRLS-_-GIRLS-BACKPACKS_22'),
                  ('baby-kids', 'toys-and-games',
                   'https://www.jcpenney.com/d/toys-and-games?cm_re=ZD-_-DEPARTMENT-BABY-KIDS-_-LF-_-BABYKIDS-TOYSGAMES-_-ToysGames_1'),
                  ('baby-kids', 'baby-gifts',
                   'https://www.jcpenney.com/g/baby/baby-gifts?id=cat100260097&cm_re=ZE-_-DEPARTMENT-BABY-KIDS-_-LF-_-BABY-GIFTS-KEEPSAKES_1'),
                  ('baby-kids', 'baby-nursing-and-feeding',
                   'https://www.jcpenney.com/g/baby/baby-nursing-and-feeding?id=cat1004440014&cm_re=ZE-_-DEPARTMENT-BABY-KIDS-_-LF-_-NURSING-FEEDING_2'),
                  ('baby-kids', 'baby-toys-games',
                   'https://www.jcpenney.com/g/baby/baby-toys-games?id=cat100260106&cm_re=ZE-_-DEPARTMENT-BABY-KIDS-_-LF-_-BABY-TOYS-GAMES_3'),
                  ('baby-kids', 'baby-nursery-gear',
                   'https://www.jcpenney.com/g/baby/baby-nursery-gear?id=cat11100000079&cm_re=ZE-_-DEPARTMENT-BABY-KIDS-_-LF-_-VIEW-ALL-BABY-GEAR_4'),
                  ('baby-kids', 'thereabouts',
                   'https://www.jcpenney.com/g/baby-kids/thereabouts?id=cat11100001545&cm_re=ZF-_-DEPARTMENT-BABY-KIDS-_-LF-_-BABYKIDS-BRANDS-_-Brands-THEREABOUTS_1'),
                  ('baby-kids', 'carters',
                   'https://www.jcpenney.com/g/baby-kids/carters?id=cat11100001546&cm_re=ZF-_-DEPARTMENT-BABY-KIDS-_-LF-_-BABYKIDS-BRANDS-_-Brands-Carters_2'),
                  ('baby-kids', 'disney',
                   'https://www.jcpenney.com/g/shops/disney?id=cat10010530001&cm_re=ZF-_-DEPARTMENT-BABY-KIDS-_-LF-_-BABYKIDS-BRANDS-_-Brands-DISNEY_3'),
                  ('baby-kids', 'nike-3brand-by-russell-wilson',
                   'https://www.jcpenney.com/g/baby-kids/nike-3brand-by-russell-wilson?id=cat11100006651&cm_re=ZF-_-DEPARTMENT-BABY-KIDS-_-LF-_-BABYKIDS-BRANDS-_-NIKE-3-BRAND-BY-RUSSELL-WILSON_4'),
                  ('baby-kids', 'okie-dokie',
                   'https://www.jcpenney.com/g/baby-kids/okie-dokie?id=cat11100001547&cm_re=ZF-_-DEPARTMENT-BABY-KIDS-_-LF-_-BABYKIDS-BRANDS-_-Brands-OkieDokie_5'),
                  ('baby-kids', 'xersion',
                   'https://www.jcpenney.com/g/baby-kids/xersion?id=cat11100001542&cm_re=ZF-_-DEPARTMENT-BABY-KIDS-_-LF-_-BABYKIDS-BRANDS-_-Brands-Xersion_6'),
                  ('baby-kids', 'baby-kids',
                   'https://www.jcpenney.com/g/baby-kids?view_all=view+all+brands&id=dept11100000014&cm_re=ZF-_-DEPARTMENT-BABY-KIDS-_-LF-_-BABYKIDS-BRANDS-_-Brands-AllBrands_7'),
                  ('baby-kids', 'character-shop',
                   'https://www.jcpenney.com/g/shops/character-shop?id=cat10010810001&cm_re=ZG-_-DEPARTMENT-BABY-KIDS-_-LF-_-BABYKIDS-SPECIALTYSHOPS-_-SpecialtyShops-CharacterShop_1'),
                  ('baby-kids', 'costume-shop',
                   'https://www.jcpenney.com/g/shops/costume-shop?id=cat1008550001&cm_re=ZG-_-DEPARTMENT-BABY-KIDS-_-LF-_-BABYKIDS-SPECIALTYSHOPS-_-SpecialtyShops-CostumeShop_2'),
                  ('baby-kids', 'birthday-holiday-shop',
                   'https://www.jcpenney.com/g/baby/birthday-holiday-shop?id=cat10010570001&cm_re=ZG-_-DEPARTMENT-BABY-KIDS-_-LF-_-BABYKIDS-SPECIALTYSHOPS-_-SpecialtyShops-BirthdayHolidayShop_3'),
                  ('baby-kids', '',
                   'https://www.jcpenney.comhttps://www.jcpportraits.com?cm_re=ZG-_-DEPARTMENT-BABY-KIDS-_-LF-_-BABYKIDS-SPECIALTYSHOPS-_-SpecialtyShops-JCPPortraits_4'),
                  ('baby-kids', 'family-pajamas',
                   'https://www.jcpenney.com/g/shops/family-pajamas?theme=family&id=cat1007690010&cm_re=ZG-_-DEPARTMENT-BABY-KIDS-_-LF-_-BABYKIDS-SPECIALTYSHOPS-_-MATCHING-FAMILY-PAJAMAS_5'),
                  ('baby-kids', '',
                   'https://www.jcpenney.comhttps://www.jcpenneyoptical.com/?cm_re=ZG-_-DEPARTMENT-BABY-KIDS-_-LF-_-BABYKIDS-SPECIALTYSHOPS-_-SpecialtyShops-Optical_6'),
                  ('baby-kids', 'bm-JCP_Kids',
                   'https://www.jcpenney.comhttp://sportsfanshop.jcpenney.com/pages/Kids/source/bm-JCP_Kids?cm_re=ZG-_-DEPARTMENT-BABY-KIDS-_-LF-_-BABYKIDS-SPECIALTYSHOPS-_-SpecialtyShops-SportsFanShop_7'),
                  ('baby-kids', 'tween',
                   'https://www.jcpenney.com/g/baby-kids/tween?id=cat11100009860&cm_re=ZG-_-DEPARTMENT-BABY-KIDS-_-LF-_-BABYKIDS-SPECIALTYSHOPS-_-TWEEN-SHOP_8'),
                  ('baby-kids', 'kids-school-uniforms',
                   'https://www.jcpenney.com/g/baby-kids/kids-school-uniforms?id=cat11100001552&cm_re=ZG-_-DEPARTMENT-BABY-KIDS-_-LF-_-BABYKIDS-SPECIALTYSHOPS-_-SpecialtyShops-UNIFORM-SHOP_9'),
                  ('baby-kids', 'baby-kids',
                   'https://www.jcpenney.com/g/baby-kids?s1_deals_and_promotions=SALE&id=dept11100000014&cm_re=ZH-_-DEPARTMENT-BABY-KIDS-_-LF-_-BABYKIDS-SALEANDPROMOTIONS-_-Sale_1'),
                  ('baby-kids', 'baby-kids',
                   'https://www.jcpenney.com/g/baby-kids?s1_deals_and_promotions=CLEARANCE&id=dept11100000014&cm_re=ZH-_-DEPARTMENT-BABY-KIDS-_-LF-_-BABYKIDS-SALEANDPROMOTIONS-_-Clearance_2')}
    categories = {('shoes', 'all-womens-shoes',
                   'https://www.jcpenney.com/g/shoes/all-womens-shoes?new_arrivals=view+all+new&id=cat100240063&cm_re=ZA-_-DEPARTMENT-SHOES-_-LF-_-NEW-ARRIVALS_1'),
                  ('shoes', 'womens-athletic-shoes',
                   'https://www.jcpenney.com/g/shoes/womens-athletic-shoes?id=cat100250192&cm_re=ZA-_-DEPARTMENT-SHOES-_-LF-_-SHOES_WomensShoes_AthleticSneakers_2'),
                  ('shoes', 'womens-boots',
                   'https://www.jcpenney.com/g/shoes/womens-boots?id=cat100250184&cm_re=ZA-_-DEPARTMENT-SHOES-_-LF-_-BOOTS_3'),
                  ('shoes', 'womens-casual-shoes',
                   'https://www.jcpenney.com/g/shoes/womens-casual-shoes?id=cat1003560003&cm_re=ZA-_-DEPARTMENT-SHOES-_-LF-_-SHOES_WomensShoes_CasualShoes_4'),
                  ('shoes', 'womens-comfort-shoes',
                   'https://www.jcpenney.com/g/shoes/womens-comfort-shoes?id=cat100240062&cm_re=ZA-_-DEPARTMENT-SHOES-_-LF-_-SHOES_WomensShoes_ComfortShoes_5'),
                  ('shoes', 'womens-pumps-heels',
                   'https://www.jcpenney.com/g/shoes/womens-pumps-heels?id=cat100250187&cm_re=ZA-_-DEPARTMENT-SHOES-_-LF-_-SHOES_WomensShoes_DRESS-SHOES_6'),
                  ('shoes', 'womens-flats-loafers',
                   'https://www.jcpenney.com/g/shoes/womens-flats-loafers?id=cat100250188&cm_re=ZA-_-DEPARTMENT-SHOES-_-LF-_-SHOES_WomensShoes_FlatsLoafers_7'),
                  ('shoes', 'womens-pumps-heels',
                   'https://www.jcpenney.com/g/shoes/womens-pumps-heels?id=cat100250187&cm_re=ZA-_-DEPARTMENT-SHOES-_-LF-_-SHOES_WomensShoes_PumpsHeels_8'),
                  ('shoes', 'womens-sandals-flip-flops',
                   'https://www.jcpenney.com/g/shoes/womens-sandals-flip-flops?id=cat100250193&cm_re=ZA-_-DEPARTMENT-SHOES-_-LF-_-SHOES_WomensShoes_SandalsFlipFlops_9'),
                  ('shoes', 'womens-slippers',
                   'https://www.jcpenney.com/g/shoes/womens-slippers?id=cat1002040018&cm_re=ZA-_-DEPARTMENT-SHOES-_-LF-_-SHOES_WomensShoes_Slippers_10'),
                  ('shoes', 'womens-boots',
                   'https://www.jcpenney.com/g/shoes/womens-boots?calf_width=wide&id=cat100250184&cm_re=ZA-_-DEPARTMENT-SHOES-_-LF-_-SHOES_WomensShoes_WideCalfBoots_11'),
                  ('shoes', 'all-womens-shoes',
                   'https://www.jcpenney.com/g/shoes/all-womens-shoes?d_width=extra+wide%7Cwide&id=cat100240063&cm_re=ZA-_-DEPARTMENT-SHOES-_-LF-_-SHOES_WomensShoes_WideWidthShoes_12'),
                  ('shoes', 'womens-work-shoes',
                   'https://www.jcpenney.com/g/shoes/womens-work-shoes?id=cat1005310003&cm_re=ZA-_-DEPARTMENT-SHOES-_-LF-_-SHOES_WomensShoes_WorkShoes_13'),
                  ('shoes', 'all-womens-shoes',
                   'https://www.jcpenney.com/g/shoes/all-womens-shoes?id=cat100240063&cm_re=ZA-_-DEPARTMENT-SHOES-_-LF-_-SHOES_WomensShoes_AllWomensShoes_14'),
                  ('shoes', 'mens-shoes',
                   'https://www.jcpenney.com/g/shoes/mens-shoes?new_arrivals=view+all+new&id=cat100300057&cm_re=ZB-_-DEPARTMENT-SHOES-_-LF-_-NEW-ARRIVALS_1'),
                  ('shoes', 'mens-athletic-shoes',
                   'https://www.jcpenney.com/g/shoes/mens-athletic-shoes?id=cat100250173&cm_re=ZB-_-DEPARTMENT-SHOES-_-LF-_-SHOES_MensShoes_AthleticSneakers_2'),
                  ('shoes', 'mens-boots',
                   'https://www.jcpenney.com/g/shoes/mens-boots?id=cat100300058&cm_re=ZB-_-DEPARTMENT-SHOES-_-LF-_-SHOES_MensShoes_Boots_3'),
                  ('shoes', 'mens-casual-shoes',
                   'https://www.jcpenney.com/g/shoes/mens-casual-shoes?id=cat100250174&cm_re=ZB-_-DEPARTMENT-SHOES-_-LF-_-SHOES_MensShoes_CasualShoes_4'),
                  ('shoes', 'mens-comfort-shoes',
                   'https://www.jcpenney.com/g/shoes/mens-comfort-shoes?id=cat100250176&cm_re=ZB-_-DEPARTMENT-SHOES-_-LF-_-SHOES_MensShoes_ComfortShoes_5'),
                  ('shoes', 'mens-dress-shoes',
                   'https://www.jcpenney.com/g/shoes/mens-dress-shoes?id=cat100250175&cm_re=ZB-_-DEPARTMENT-SHOES-_-LF-_-SHOES_MensShoes_DressShoes_6'),
                  ('shoes', 'mens-sandals-flip-flops',
                   'https://www.jcpenney.com/g/shoes/mens-sandals-flip-flops?id=cat100300059&cm_re=ZB-_-DEPARTMENT-SHOES-_-LF-_-SHOES_MensShoes_SandalsFlipFlops_7'),
                  ('shoes', 'mens-slippers',
                   'https://www.jcpenney.com/g/shoes/mens-slippers?id=cat100300060&cm_re=ZB-_-DEPARTMENT-SHOES-_-LF-_-SHOES_MensShoes_Slippers_8'),
                  ('shoes', 'mens-shoes',
                   'https://www.jcpenney.com/g/shoes/mens-shoes?d_width=wide&id=cat100300057&cm_re=ZB-_-DEPARTMENT-SHOES-_-LF-_-SHOES_MensShoes_WideWidthShoes_9'),
                  ('shoes', 'mens-work-shoes',
                   'https://www.jcpenney.com/g/shoes/mens-work-shoes?id=cat1005040027&cm_re=ZB-_-DEPARTMENT-SHOES-_-LF-_-SHOES_MensShoes_WorkShoes_10'),
                  ('shoes', 'mens-shoes',
                   'https://www.jcpenney.com/g/shoes/mens-shoes?id=cat100300057&cm_re=ZB-_-DEPARTMENT-SHOES-_-LF-_-SHOES_MensShoes_AllMensShoes_11'),
                  ('shoes', 'all-kids-shoes',
                   'https://www.jcpenney.com/g/shoes/all-kids-shoes?new_arrivals=view+all+new&id=cat100470027&cm_re=ZC-_-DEPARTMENT-SHOES-_-LF-_-NEW-ARRIVALS_1'),
                  ('shoes', 'all-kids-shoes',
                   'https://www.jcpenney.com/g/shoes/all-kids-shoes?product_type=sandals&id=cat100470027&cm_re=ZC-_-DEPARTMENT-SHOES-_-LF-_-KIDS-SANDALS_2'),
                  ('shoes', 'girls-shoes',
                   'https://www.jcpenney.com/g/shoes/girls-shoes?id=cat100250179&cm_re=ZC-_-DEPARTMENT-SHOES-_-LF-_-SHOES_KidsShoes_GirlsShoes_3'),
                  ('shoes', 'boys-shoes',
                   'https://www.jcpenney.com/g/shoes/boys-shoes?id=cat100250180&cm_re=ZC-_-DEPARTMENT-SHOES-_-LF-_-SHOES_KidsShoes_BoysShoes_4'),
                  ('shoes', 'infant-toddler-shoes',
                   'https://www.jcpenney.com/g/shoes/infant-toddler-shoes?id=cat1004090073&cm_re=ZC-_-DEPARTMENT-SHOES-_-LF-_-SHOES_KidsShoes_BabyToddlerShoes_5'),
                  ('shoes', 'girls-shoes',
                   'https://www.jcpenney.com/g/shoes/girls-shoes?product_type=athletic+shoes&id=cat100250179&cm_re=ZC-_-DEPARTMENT-SHOES-_-LF-_-SHOES_KidsShoes_GirlsAthleticShoes_6'),
                  ('shoes', 'all-dress-shoes',
                   'https://www.jcpenney.com/g/shoes/all-dress-shoes?gender=girls&id=cat1003790028&cm_re=ZC-_-DEPARTMENT-SHOES-_-LF-_-SHOES_KidsShoes_GirlsDressShoes_7'),
                  ('shoes', 'girls-shoes',
                   'https://www.jcpenney.com/g/shoes/girls-shoes?product_type=boots&id=cat100250179&cm_re=ZC-_-DEPARTMENT-SHOES-_-LF-_-SHOES_KidsShoes_GirlsBoots_8'),
                  ('shoes', 'boys-shoes',
                   'https://www.jcpenney.com/g/shoes/boys-shoes?product_type=athletic+shoes&id=cat100250180&cm_re=ZC-_-DEPARTMENT-SHOES-_-LF-_-SHOES_KidsShoes_BoysAthleticShoes_9'),
                  ('shoes', 'boys-shoes',
                   'https://www.jcpenney.com/g/shoes/boys-shoes?occasion=dress&id=cat100250180&cm_re=ZC-_-DEPARTMENT-SHOES-_-LF-_-SHOES_KidsShoes_BoysDressShoes_10'),
                  ('shoes', 'boys-shoes',
                   'https://www.jcpenney.com/g/shoes/boys-shoes?product_type=boots&id=cat100250180&cm_re=ZC-_-DEPARTMENT-SHOES-_-LF-_-SHOES_KidsShoes_BoysBoots_11'),
                  ('shoes', 'all-kids-shoes',
                   'https://www.jcpenney.com/g/shoes/all-kids-shoes?id=cat100470027&cm_re=ZC-_-DEPARTMENT-SHOES-_-LF-_-SHOES_KidsShoes_AllKidsShoes_12'),
                  ('shoes', 'shoes-handbags-accessories',
                   'https://www.jcpenney.com/g/shops/trends/shoes-handbags-accessories?id=cat11100018692&cm_re=ZD-_-DEPARTMENT-SHOES-_-LF-_-SHOP-ALL-TRENDS_2'),
                  ('shoes', 'shoes-handbags-accessories',
                   'https://www.jcpenney.com/g/shops/trends/shoes-handbags-accessories?trends=all+about+bows&id=cat11100018692&cm_re=ZD-_-DEPARTMENT-SHOES-_-LF-_-ALL-ABOUT-BOWS_3'),
                  ('shoes', 'shoes-handbags-accessories',
                   'https://www.jcpenney.com/g/shops/trends/shoes-handbags-accessories?trends=color+pop&id=cat11100018692&cm_re=ZD-_-DEPARTMENT-SHOES-_-LF-_-BRIGHT-HUES_4'),
                  ('shoes', 'shoes-handbags-accessories',
                   'https://www.jcpenney.com/g/shops/trends/shoes-handbags-accessories?trends=denim&id=cat11100018692&cm_re=ZD-_-DEPARTMENT-SHOES-_-LF-_-DENIM_5'),
                  ('shoes', 'shoes-handbags-accessories',
                   'https://www.jcpenney.com/g/shops/trends/shoes-handbags-accessories?trends=metallic&id=cat11100018692&cm_re=ZD-_-DEPARTMENT-SHOES-_-LF-_-METALLIC_6'),
                  ('shoes', 'shoes-handbags-accessories',
                   'https://www.jcpenney.com/g/shops/trends/shoes-handbags-accessories?trends=natural&id=cat11100018692&cm_re=ZD-_-DEPARTMENT-SHOES-_-LF-_-NATURAL-CROCHET_7'),
                  ('shoes', 'shoes',
                   'https://www.jcpenney.com/g/shoes?brand=adidas&id=dept20000018&cm_re=ZE-_-DEPARTMENT-SHOES-_-LF-_-ADIDAS_1'),
                  ('shoes', 'all-womens-shoes',
                   'https://www.jcpenney.com/g/shoes/all-womens-shoes?brand=a.n.a&id=cat100240063&cm_re=ZE-_-DEPARTMENT-SHOES-_-LF-_-A-N-A_2'),
                  ('shoes', 'shoes',
                   'https://www.jcpenney.com/g/shoes?brand=arizona&id=dept20000018&cm_re=ZE-_-DEPARTMENT-SHOES-_-LF-_-SHOES_Brands_Arizona_3'),
                  ('shoes', 'shoes',
                   'https://www.jcpenney.com/g/shoes?brand=clarks&id=dept20000018&cm_re=ZE-_-DEPARTMENT-SHOES-_-LF-_-SHOES_Brands_Clarks_4'),
                  ('shoes', 'shoes',
                   'https://www.jcpenney.com/g/shoes?brand=deer+stags&id=dept20000018&cm_re=ZE-_-DEPARTMENT-SHOES-_-LF-_-DEER-STAGS_5'),
                  ('shoes', 'all-athletic-shoes',
                   'https://www.jcpenney.com/g/shoes/all-athletic-shoes?brand=fila&id=cat100260221&cm_re=ZE-_-DEPARTMENT-SHOES-_-LF-_-SHOES_Brands_Fila_6'),
                  ('shoes', 'shoes',
                   'https://www.jcpenney.com/g/shoes?brand=frye+and+co&id=dept20000018&cm_re=ZE-_-DEPARTMENT-SHOES-_-LF-_-FRYE-AND-CO_7'),
                  ('shoes', 'mens-shoes',
                   'https://www.jcpenney.com/g/shoes/mens-shoes?brand=j.+ferrar&id=cat100300057&cm_re=ZE-_-DEPARTMENT-SHOES-_-LF-_-J-FERRAR_8'),
                  ('shoes', 'all-womens-shoes',
                   'https://www.jcpenney.com/g/shoes/all-womens-shoes?brand=journee+collection&id=cat100240063&cm_re=ZE-_-DEPARTMENT-SHOES-_-LF-_-JOURNEE-COLLECTION_9'),
                  ('shoes', 'shoes',
                   'https://www.jcpenney.com/g/shoes?brand=liz+claiborne&id=dept20000018&cm_re=ZE-_-DEPARTMENT-SHOES-_-LF-_-SHOES_Brands_LizClaiborne_10'),
                  ('shoes', 'shoes',
                   'https://www.jcpenney.com/g/shoes?brand=mixit&view_all=view+all+brands&id=dept20000018&cm_re=ZE-_-DEPARTMENT-SHOES-_-LF-_-MIXIT_11'),
                  ('shoes', 'mens-shoes',
                   'https://www.jcpenney.com/g/shoes/mens-shoes?brand=mutual+weave&id=cat100300057&cm_re=ZE-_-DEPARTMENT-SHOES-_-LF-_-MUTUAL-WEAVE_12'),
                  ('shoes', 'shoes',
                   'https://www.jcpenney.com/g/shoes?brand=puma&id=dept20000018&cm_re=ZE-_-DEPARTMENT-SHOES-_-LF-_-Shoes_Brands_Puma_13'),
                  ('shoes', 'all-athletic-shoes',
                   'https://www.jcpenney.com/g/shoes/all-athletic-shoes?brand=reebok&id=cat100260221&cm_re=ZE-_-DEPARTMENT-SHOES-_-LF-_-Shoes_Brands_Reebok_14'),
                  ('shoes', 'shoes',
                   'https://www.jcpenney.com/g/shoes?brand=skechers&id=dept20000018&cm_re=ZE-_-DEPARTMENT-SHOES-_-LF-_-SHOES_Brands_Skechers_15'),
                  ('shoes', 'mens-shoes',
                   'https://www.jcpenney.com/g/shoes/mens-shoes?brand=stafford&id=cat100300057&cm_re=ZE-_-DEPARTMENT-SHOES-_-LF-_-STAFFORD_16'),
                  ('shoes', 'kids-shoes',
                   'https://www.jcpenney.com/g/shoes/kids-shoes?brand=thereabouts&id=cat100470027&cm_re=ZE-_-DEPARTMENT-SHOES-_-LF-_-THEREABOUTS_17'),
                  ('shoes', 'shoes',
                   'https://www.jcpenney.com/g/shoes?view_all=view+all+brands&id=dept20000018&cm_re=ZE-_-DEPARTMENT-SHOES-_-LF-_-SHOES_Brands_ViewAllBrands_18'),
                  ('shoes', 'shoes',
                   'https://www.jcpenney.com/g/shoes?s1_deals_and_promotions=SALE&id=dept20000018&cm_re=ZF-_-DEPARTMENT-SHOES-_-LF-_-SHOES_SalePromotion_Sales_1'),
                  ('shoes', 'shoes',
                   'https://www.jcpenney.com/g/shoes?s1_deals_and_promotions=CLEARANCE&id=dept20000018&cm_re=ZF-_-DEPARTMENT-SHOES-_-LF-_-SHOES_SalePromotion_Clearance_2')}
    with ProcessPoolExecutor(max_workers=num_processes) as executor:
        tasks = [loop.run_in_executor(executor, async_runner, main_category, sub_category) for
                 main_category, sub_category, _ in categories]
        task_results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in task_results:
            if isinstance(result, Exception):
                log.error(f"{result}")


def async_runner(main_category, sub_category):
    asyncio.run(run(main_category, sub_category))


if __name__ == "__main__":
    asyncio.run(main())
