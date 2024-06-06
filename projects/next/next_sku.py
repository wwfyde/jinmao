import asyncio
import re
import uuid

import httpx
import structlog
from playwright.async_api import Playwright, async_playwright, BrowserContext, Response, Page

from crawler.config import settings
from crawler.store import save_sku_data, save_product_data, save_review_data

PLAYWRIGHT_TIMEOUT = settings.playwright.timeout
print(f"{PLAYWRIGHT_TIMEOUT=}")
log = structlog.get_logger()


async def run(playwright: Playwright) -> None:
    # 从playwright对象中获取chromium浏览器
    chromium = playwright.chromium
    user_data_dir = settings.user_data_dir
    if settings.save_login_state:
        context = await playwright.chromium.launch_persistent_context(
            user_data_dir,
            headless=False,
            # headless=False,
            # slow_mo=50,  # 每个操作的延迟时间（毫秒），便于调试
            # args=["--start-maximized"],  # 启动时最大化窗口
            # ignore_https_errors=True,  # 忽略HTTPS错误
            # devtools=True,
        )
    else:
        browser = await chromium.launch(
            headless=True,
            devtools=True,
        )
        context = await browser.new_context()

    # 设置全局超时
    context.set_default_timeout(PLAYWRIGHT_TIMEOUT)
    # 并发打开新的页面
    # semaphore = asyncio.Semaphore(settings.playwright.concurrency or 10)
    # tasks = []
    # for i in range(10):
    #     tasks.append(open_pdp_page(context, semaphore))
    # pages = await asyncio.gather(*tasks)
    page = await context.new_page()
    page.set_default_timeout(PLAYWRIGHT_TIMEOUT)
    async with page:
        # route_event = asyncio.Event()

        async def handle_response(response: Response):
            if "https://api.bazaarvoice.com/data/reviews.json" in response.url and response.status == 200:
                reviews = await response.json()
                print(f"{reviews=}")

        # await page.route("**/api.bazaarvoice.com/data/**", handle_route)
        page.on("response", handle_response)
        url = "https://www.next.co.uk/g29253s3/709159"
        url = "https://www.next.us/en/style/st423998/981678"
        url = "https://www.next.co.uk/g29529s4/185342"
        # url = "https://www.next.co.uk/style/su051590/884625"
        # url = "https://www.next.co.uk/style/su179185/k73610"
        # url = "https://www.next.co.uk/style/SU054491/176332"
        await page.goto(
            url=url,
            timeout=PLAYWRIGHT_TIMEOUT,
            wait_until="load",
        )
        # 单击review按钮以加载评论
        log.info("等待评论按钮出现")
        # 可能没有评论
        # review_node = await page.wait_for_selector('//*[@id="LoadMoreBtn"]', timeout=5000)
        # if review_node is None:
        #     print("该商品没有评论")
        await page.wait_for_load_state(timeout=30000)
        # 获取product_style 信息

        product_obj = await parse_next_product(page)

        print(f"从Page中解析 商品信息{product_obj=}")

        sku_id_raw = product_obj.get("sku_id_raw")
        print(f"源sku_id: {sku_id_raw}")
        # 获取数据信息
        shot_data: dict = await page.evaluate("""() => {
                            return window.shotData;
                        }""")
        # print(type(shot_data))
        # print(shot_data.get("Styles"))
        sku = await parse_next_sku(
            shot_data,
            sku_id_raw,
            product_id=product_obj.get(
                "product_id",
            ),
            product_name=product_obj.get("product_name"),
            sku_url=page.url,
            source="next",
        )
        print(f"商品SKU信息: {sku=}")
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
                print("点击完成")
                await page.wait_for_timeout(2000)
                await page.wait_for_load_state("domcontentloaded", timeout=3000)
                print("等待加载完成")
            except Exception as exc:
                log.info(f"没有更多评论可加载: {exc}")
                break
            # content = await page.content()
            # 获取评论列表

        reviews = await parse_review_from_dom(page)

        log.debug(f"共获取到{len(reviews)}, {reviews=}")
        await page.pause()
        log.info("点击评论按钮")
        # await page.locator("#accordion-button-0").click()
        await page.wait_for_load_state("load", timeout=60000)
        # await route_event.wait()
        log.info("等待事件被正确执行")

        print("页面加载完成")
        pass
        # await page.pause()


async def open_pdp_page(context: BrowserContext, semaphore: asyncio.Semaphore, product_id: str, sku_id: str):
    async with semaphore:
        page = await context.new_page()
        page.set_default_timeout(PLAYWRIGHT_TIMEOUT)
        return sku_id


async def parse_review_from_dom(page: Page, product_id: str = None, source: str = None):
    """
    Next 只能通过DOM获取评论, 然后通过点击按钮加载更多评论
    """
    # 获取商品信息
    # 商品ID
    sku_id = httpx.URL(page.url).path.split("/")[-1]
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

    # print(f"{rating=}")
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
        # print(f"{rating=}")
        # print(f"{rating_text=}")
        # print(f"{rating_url=}")
        # print(f"{username=}")
        # print(f"{review=}")
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
    print("找到商品信息")

    def find_target_item(styles, sku_id_raw):
        for style in styles:
            for fit in style.get("Fits", []):
                for item in fit.get("Items", []):
                    if item["ItemNumber"] == sku_id_raw:
                        return item
        return None

    item = find_target_item(pdp_style, sku_id_raw)
    # print(f"从数据中检查SKU信息{item}")
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
        washing_instructions=washing_instructions,
    )
    # 将sku 入库到数据库
    save_sku_data(sku)
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
    print(f"{sku_id=}")
    print(f"{product_id=}")
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
    save_product_data(product_obj)
    return product_obj


async def main():
    async with async_playwright() as p:
        await run(p)


if __name__ == "__main__":
    asyncio.run(main())
