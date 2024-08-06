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
            slow_mo=50, headless=PLAYWRIGHT_HEADLESS, args=["--single-process"], timeout=60000,
            proxy=proxy,

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
        r = redis.from_url(settings.redis_dsn, decode_responses=True, protocol=3)
        key = f"{source}:{main_categories}:{sub_categories}"
        async with r:
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
                )
            )

        task_results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in task_results:
            if isinstance(result, Exception):
                log.error(f"{result}")
        await context.close()


async def open_pdp_page(
        context: BrowserContext,
        semaphore: asyncio.Semaphore,
        url: str,
        *,
        source: str = "jcpenney",
        main_category: str = None,
        sub_category: str = None
):
    async with semaphore:
        page = await context.new_page()
        page.set_default_timeout(PLAYWRIGHT_TIMEOUT)
        product_id = httpx.URL(url).path.split("/")[-1]  # 获取商品ID

        # 临时储存商品信息目录
        product_folder = settings.data_dir.joinpath(source, "products")
        product_folder.mkdir(exist_ok=True, parents=True)
        product_file = product_folder.joinpath(f"product_{product_id}.json")
        # 临时储存评论目录
        reviews_folder = settings.data_dir.joinpath(source, "reviews")
        reviews_folder.mkdir(exist_ok=True, parents=True)
        reviews_file = reviews_folder.joinpath(f"reviews_{product_id}.json")

        # TODO 优化去重跳过逻辑
        r = redis.from_url(settings.redis_dsn, decode_responses=True, protocol=3)
        key = f"status:{source}:{product_id}"
        async with r:
            product_status = await r.get(key)
            if product_status == "done":
                log.info(f"已经抓取过产品 {product_id=}")
                return product_id

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
                    'pets', 'furniture', 'household', 'outdoor-living-garden') else 'unknown',  # 大类别,
                main_category=main_category,
                sub_category=sub_category,
                lot_id=lot_id,
            )

            if product_details:
                product_name = product_details.get("name")
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
                        outer_image_urls=model_image_urls,
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
    num_processes = 4

    log.info(f"CPU核心数: {os.cpu_count()}, 进程数: {num_processes}")
    categories = [
        # ("men", "default"),
        ("men", "shirts"),
    ]
    categories = [
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
    ]
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
