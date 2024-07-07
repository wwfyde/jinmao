import asyncio
import html
import re
import uuid

import dateutil.parser
import httpx
import redis.asyncio as redis
from bs4 import BeautifulSoup
from playwright.async_api import Playwright, async_playwright, BrowserContext, Response, Page

from crawler import log
from crawler.config import settings
from crawler.store import save_sku_data, save_product_data, save_review_data

PLAYWRIGHT_TIMEOUT = settings.playwright.timeout
log.debug(f"{PLAYWRIGHT_TIMEOUT=}")


async def run(playwright: Playwright) -> None:
    # 从playwright对象中获取chromium浏览器
    chromium = playwright.chromium
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
            headless=settings.playwright.headless,
            proxy=proxy,
            # headless=False,
            # slow_mo=50,  # 每个操作的延迟时间（毫秒），便于调试
            # args=["--start-maximized"],  # 启动时最大化窗口
            # ignore_https_errors=True,  # 忽略HTTPS错误
            # devtools=True,
        )
    else:
        browser = await chromium.launch(
            headless=settings.playwright.headless,
            devtools=True,
            proxy=proxy,
        )
        context = await browser.new_context()

    # 设置全局超时
    context.set_default_timeout(PLAYWRIGHT_TIMEOUT)
    # 并发打开新的页面
    semaphore = asyncio.Semaphore(settings.playwright.concurrency or 10)
    log.debug(f"并发请求数: {settings.playwright.concurrency or 10}")

    # tasks = []
    # for i in range(10):
    #     tasks.append(open_pdp_page(context, semaphore))
    # pages = await asyncio.gather(*tasks)
    # log.debug(f"{pages=}")
    # TODO 从redis 中获取商品列表
    # 获取商品列表

    r = redis.from_url(settings.redis_dsn, decode_responses=True, protocol=3)
    async with r:
        source = "next"
        main_category = "women"
        sub_category = "joggers"
        product_urls = await r.smembers(f"{source}:{main_category}:{sub_category}")
        log.debug(product_urls, len(product_urls))
        # product_urls = ["https://www.next.co.uk/style/su272671/q64927#q64927"]
        tasks = [
            open_pdp_page(
                context, semaphore, url, main_category=main_category, source=source, sub_category=sub_category
            )
            for url in product_urls
        ]
        results = await asyncio.gather(*tasks)
        log.debug(f"{results=}")

    # await context.close()
    # await asyncio.Future()
    await asyncio.sleep(10)


async def open_pdp_page(
    context: BrowserContext,
    semaphore: asyncio.Semaphore,
    url: str,
    *,
    main_category: str,
    sub_category: str,
    source: str,
):
    """
    打开产品详情页PDP
    """
    async with semaphore:
        page = await context.new_page()
        page.set_default_timeout(PLAYWRIGHT_TIMEOUT)
        async with page:
            # route_event = asyncio.Event()
            await page.route(
                "**/*",
                lambda route: route.abort() if route.request.resource_type == "image" else route.continue_(),
            )

            async def handle_response(response: Response):
                if "https://api.bazaarvoice.com/data/reviews.json" in response.url and response.status == 200:
                    reviews = await response.json()
                    log.debug(f"{reviews=}")

            # await page.route("**/api.bazaarvoice.com/data/**", handle_route)
            page.on("response", handle_response)
            # url = "https://www.next.co.uk/g29253s3/709159"
            # url = "https://www.next.us/en/style/st423998/981678"
            # url = "https://www.next.co.uk/g29529s4/185342"
            # # url = "https://www.next.co.uk/style/su051590/884625"
            # # url = "https://www.next.co.uk/style/su179185/k73610"
            # # url = "https://www.next.co.uk/style/SU054491/176332"
            # url = "https://www.next.co.uk/style/su272671/q64927#q64927"
            await page.goto(
                url=url,
                timeout=PLAYWRIGHT_TIMEOUT,
                wait_until="load",
            )
            # 通过url 解析 product_id 和 sku_id
            url_paths = httpx.URL(url).path.split("/")
            product_id = url_paths[-2].lower()
            sku_id = url_paths[-1].lower()
            # 单击review按钮以加载评论
            log.info("等待评论按钮出现")
            # 可能没有评论
            # review_node = await page.wait_for_selector('//*[@id="LoadMoreBtn"]', timeout=5000)
            # if review_node is None:
            #     log.debug("该商品没有评论")
            await page.wait_for_load_state(timeout=30000)
            # 获取product_style 信息
            product = await parse_next_product(page)

            log.debug(f"从Page中解析 商品信息{product=}")

            sku_id_raw = product.get("sku_id_raw")
            product.update(dict(gender=main_category, sub_category=sub_category, source=source))
            save_product_data(product)

            log.debug(f"源sku_id: {sku_id_raw}")
            # 获取数据信息
            shot_data: dict = await page.evaluate("""() => {
                                return window.shotData;
                            }""")
            # log.debug(type(shot_data))
            # log.debug(shot_data.get("Styles"))
            sku = await parse_next_sku(
                shot_data,
                sku_id_raw,
                product_id=product_id,
                product_name=product.get("product_name"),
                sku_url=page.url,
                source="next",
            )
            log.debug(f"商品SKU信息: {sku=}")
            # 通过点击按钮加载更多评论
            while True:
                try:
                    review_button = page.locator('//*[@id="LoadMoreBtn"]')
                    if await review_button.count() == 0:
                        log.info("没有额外评论需要展开")
                        break
                    display = await page.locator('//*[@id="LoadMoreBtn"]').get_attribute("style")
                    class_ = await page.locator('//*[@id="LoadMoreBtn"]').get_attribute("class")
                    log.debug(f"按钮的 class 属性为: {class_}")
                    log.debug(f"按钮的 display 属性为: {display}")

                    # TODO 可优化 review_button.is_visible():
                    if display and "display: none;" in display:
                        log.info("按钮的 display 属性为 none，退出循环")
                        break

                    await page.locator('//*[@id="LoadMoreBtn"]').first.click()
                    log.debug("点击完成")
                    await page.wait_for_timeout(2000)
                    await page.wait_for_load_state("domcontentloaded", timeout=3000)
                    log.debug("等待加载完成")
                except Exception as exc:
                    log.info(f"没有更多评论可加载: {exc}")
                    break
                # content = await page.content()
                # 获取评论列表

            reviews = await parse_review_from_dom(page, product_id=product_id, sku_id=sku_id)

            log.debug(f"共获取到{len(reviews)}, {reviews=}")
            # await page.pause()
            log.info("点击评论按钮")
            # await page.locator("#accordion-button-0").click()
            await page.wait_for_load_state("load", timeout=60000)
            # await route_event.wait()
            log.info("等待事件被正确执行")

            log.debug("页面加载完成")
            pass
            # await page.pause()
        # TODO 当任务完成后, 标记任务状态
        return url


async def parse_review_from_dom(page: Page, product_id: str = None, sku_id: str = None, source: str = None):
    """
    Next 只能通过DOM获取评论, 然后通过点击按钮加载更多评论
    """
    # 获取商品信息
    # 商品ID
    # sku_id = httpx.URL(page.url).path.split("/")[-1]
    # 商品名称
    product_name_locator = page.locator("article > section > div.StyleHeader > div.Title > h1")
    if await product_name_locator.count() > 0:
        product_name = await product_name_locator.inner_text()
    else:
        product_name = None
    # 评分
    # rating = await page.locator(
    #     "article > section > div.StyleMeta.Meta709159 > div.Reviews.mod-pdp-reviewstars > span.Rating > span"
    # ).get_attribute("data-starrating")
    review_count_text_locator = page.locator("//article/section/div[3]/div[1]/span[2]/a[1]/span")
    if await review_count_text_locator.count() > 0:
        review_count_text = await review_count_text_locator.inner_text()
        match = re.search(r"\((\d+)\)", review_count_text)
        review_count = match.group(1) if match else 0
    else:
        review_count = 0
    log.debug(f"通过DOM获取评论数量{review_count}")

    # log.debug(f"{rating=}")
    # 获取评论数据
    # tree = etree.HTML(content)
    review_elements = page.locator("#EmbeddedReviewsContainer > div > div.reviewContent > div.userReviews > ul > li")
    reviews_count = await review_elements.count()
    log.debug(f"通过locator计算评论数量: {reviews_count}")
    reviews = []
    for i in range(reviews_count):
        review = await review_elements.nth(i).locator(".reviewText > p").inner_text()
        username = await review_elements.nth(i).locator(".username").inner_text()
        rating_text = await review_elements.nth(i).locator(".reviewStats > img").get_attribute("alt")
        rating_url = await review_elements.nth(i).locator(".reviewStats > img").get_attribute("src")
        rating = rating_url.split("/")[-1].split(".")[0] if rating_url else None
        created_at_raw = await review_elements.nth(i).locator(".reviewStats > .date").inner_text()

        log.debug(f"日期: {created_at_raw=}")
        created_at_obj = dateutil.parser.parse(created_at_raw)
        created_at = created_at_obj.strftime("%Y-%m-%d")
        log.debug(f"日期对象: {created_at_obj}")
        log.debug(f"格式化后的日期字符串: {created_at}")
        # log.debug(f"{rating=}")
        # log.debug(f"{rating_text=}")
        # log.debug(f"{rating_url=}")
        # log.debug(f"{username=}")
        # log.debug(f"{review=}")
        review = dict(
            nickname=username,
            review_id=str(uuid.uuid4()),
            source=source or "next",
            product_id=product_id,
            sku_id=sku_id,
            product_name=product_name,
            title=review,
            comment=review,
            rating_text=rating_text,
            rating_url=rating_url,
            helpful_votes=None,  # 没有按顶数
            not_helpful_votes=None,  # 没有按踩数
            created_at=created_at,
            rating=rating,
        )

        reviews.append(review)
    save_review_data(reviews)
    return reviews

    pass


async def parse_next_sku(
    pdp: dict,
    sku_id_raw: str | None = None,
    product_id: str | None = None,
    product_name: str | None = None,
    source: str | None = None,
    sku_url: str | None = None,
) -> dict | None:
    """
    从API中解析SKU信息
    next 中 sku_id =product_id
    """

    # 获取SKU信息
    # Convert the data to a benedict object
    pdp_style: list = pdp.get("Styles") if pdp.get("Styles") else []
    if not pdp_style:
        log.warning("未找到商品信息")
        return None

    # b_dict = benedict(pdp_style)

    # Extract the target value
    # target = sku_id_raw or b_dict.get("Target")

    # Function to find the target item in the Fits list
    log.debug("找到商品信息")

    def find_target_item(styles, sku_id_raw):
        for style in styles:
            for fit in style.get("Fits", []):
                for item in fit.get("Items", []):
                    if item["ItemNumber"] == sku_id_raw:
                        return item
        return None

    item = find_target_item(pdp_style, sku_id_raw)
    # log.debug(f"从数据中检查SKU信息{item}")
    if item is None:
        return None
    sku_id = item.get("ItemNumber").replace("-", "") if item.get("ItemNumber", "") else None
    color = item.get("Colour", None)
    size = item.get("Size", None)
    image_url = item.get("ShotImage", None)
    price = item.get("SalePlainPrice", None)
    original_price = item.get("FullPrice", None)
    material = item.get("Composition", None)
    pdp_url = None
    washing_instructions = item.get("WashingInstructions", None)  # 是否可清洗
    care_instructions = item.get("CareInformation", None)  # 护理指导
    department = item.get("Department", None)  # 护理指导
    origin = item.get("CountryOfOrigin", None)
    source = source or "next"
    webdata = item.get("WebData", [])[0].get("Value") if item.get("WebData") else ""
    if webdata:
        data = html.unescape(webdata)
        soup = BeautifulSoup(data, "html.parser")
        p_content = soup.find("p")
        description = p_content.get_text() if p_content else None

        # 提取 <li> 标签中的内容
        li_tags = soup.find_all("li")
        attributes = [li.get_text() for li in li_tags]
    else:
        description = None
        attributes = None

    sku = dict(
        sku_id=sku_id,
        product_id=product_id,
        product_name=product_name,
        color=color,
        sku_name=color,
        source=source,
        price=price,
        original_price=original_price,
        material=material,
        sku_url=sku_url,
        pdp_url=sku_url,
        size=size,
        image_url=image_url,
        origin=origin,
        department=department,
        care_instructions=care_instructions,
        description=description,
        attributes=attributes,
        washing_instructions=washing_instructions,
    )
    # 将sku 入库到数据库
    save_sku_data(sku)
    save_product_data(dict(product_id=product_id, source=source, attributes=attributes))
    return sku


async def parse_next_product(page: Page) -> dict | None:
    """
    从DOM中解析商品信息
    """
    article_locator = page.locator("article")
    product_id = await article_locator.get_attribute("data-stylenumber")

    sku_id_raw = await article_locator.get_attribute("data-targetitem")
    sku_id = sku_id_raw.replace("-", "") if sku_id_raw else None
    product_name = await article_locator.get_attribute("data-itemname")
    department = await article_locator.get_attribute("data-department")
    gender = await article_locator.get_attribute("data-gender")
    color = await article_locator.get_attribute("data-colour")
    product_default_color = await article_locator.get_attribute("data-defaultitemcolour")
    brand = await article_locator.get_attribute("data-brand")
    category = await article_locator.get_attribute("data-category")
    log.debug(f"{sku_id=}")
    log.debug(f"{product_id=}")
    # await page.pause()
    # 商品对象
    product_obj = dict(
        product_id=product_id,
        source="next",
        sku_id=sku_id,
        sku_id_raw=sku_id_raw,
        product_name=product_name,
        department=department,
        gender=gender,
        color=color,
        brand=brand,
        category=category,
    )
    return product_obj


async def main():
    async with async_playwright() as p:
        await run(p)


if __name__ == "__main__":
    asyncio.run(main())
