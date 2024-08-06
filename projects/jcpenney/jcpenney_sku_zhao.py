import asyncio
import json
from pathlib import Path
import time

from loguru import logger
import httpx
from playwright.async_api import (
    async_playwright,
    BrowserContext,
    Route,
    TimeoutError as PlaywrightTimeoutError,
)

from crawler.config import settings
from crawler.store import save_review_data, save_product_data
from projects.jcpenney.common import cancel_requests

PLAYWRIGHT_TIMEOUT = settings.playwright.timeout
IMAGE_POSTFIX = "?hei=1500&wid=1500&op_usm=.4%2C.8%2C0%2C0&resmode=sharp2&op_sharpen=1"
SOURCE = "jcpenney"


async def run(
        urls: list,
) -> None:
    async with async_playwright() as playwright:
        chromium = playwright.chromium
        user_data_dir = settings.user_data_dir
        # if settigs.save_login_state:
        #     context = await playwright.chromium.launch_persistent_context(
        #         user_data_dir,
        #         headless=False,
        #         # headless=False,
        #         slow_mo=50,  # 每个操作的延迟时间（毫秒），便于调试
        #         args=["--single-process"],  # 启动时最大化窗口
        #         ignore_https_errors=True,  # 忽略HTTPS错误
        #         devtools=True,
        #     )
        # else:
        #     browser = await chromium.launch(
        #         slow_mo=50, headless=True, args=["--single-process"]
        #     )
        #     context = await browser.new_context()

        browser = await chromium.launch(
            slow_mo=50, headless=False, args=["--single-process"], timeout=60000
        )
        context = await browser.new_context()

        # 设置全局超时
        semaphore = asyncio.Semaphore(settings.playwright.concurrency or 10)

        source = SOURCE
        gender = "women"
        tasks = []

        for url in urls:
            try:
                tasks.append(
                    open_pdp_page(
                        context,
                        semaphore,
                        url=url,
                        source=source,
                        gender=gender,
                    )
                )
            except Exception as e:
                logger.error(f"{url=} {e}")

        await asyncio.gather(*tasks, return_exceptions=True)
        await context.close()


async def open_pdp_page(
        context: BrowserContext,
        semaphore: asyncio.Semaphore,
        url: str,
        source: str = SOURCE,
        gender: str = None,
):
    async with semaphore:
        page = await context.new_page()
        page.set_default_timeout(PLAYWRIGHT_TIMEOUT)
        product_id = httpx.URL(url).path.split("/")[-1]

        # 临时储存商品信息目录
        product_folder = "projects/jcpenney/products"
        product_file = f"{product_folder}/product_{product_id}.json"
        # 临时储存评论目录
        reviews_folder = "projects/jcpenney/reviews"
        reviews_file = f"{reviews_folder}/reviews_{product_id}.json"

        # TODO 优化去重跳过逻辑
        need_crawl = True
        if Path(product_file).exists():
            log.info(f"已经抓取过产品 {product_id=}")
            need_crawl = False
            await page.wait_for_timeout(500)
            await page.close()
            return

        need_review = True
        if Path(reviews_file).exists():
            log.info(f"已经抓取过评论 {product_id=}")
            need_review = False

        if not need_crawl and not need_review:
            await page.close()
            return

        route_event = asyncio.Event()

        async def handle_route(route: Route):
            request = route.request
            # 处理用户评论
            if "reviews.json" in request.url:
                response = await route.fetch()
                reviews_dict = await response.json()
                reviews, total_count = parse_review_from_api(reviews_dict)
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

                new_reviews = await asyncio.gather(*tasks)
                for review in new_reviews:
                    reviews.extend(review)

                # 保存到本地进行处理
                Path(reviews_folder).mkdir(exist_ok=True, parents=True)
                with open(reviews_file, "w", encoding="utf-8") as f:
                    f.write(json.dumps(reviews, indent=4, ensure_ascii=False))

            route_event.set()

        await cancel_requests(page)
        await page.route("**/api.bazaarvoice.com/data/**", handle_route)

        try:
            await page.goto(
                url=url,
                timeout=PLAYWRIGHT_TIMEOUT,
            )

            preloaded_state: dict = await page.evaluate(
                """() => {
                                                        return window.__PRELOADED_STATE__;
                                                    }"""
            )

            sku_id = (
                preloaded_state.get("queryParams").get("selectedSKUId")
                if preloaded_state.get("queryParams")
                else None
            )

            try:
                lot_id_element = page.locator(
                    'div[data-automation-id="bazaar-voice"] + span'
                )
                await lot_id_element.wait_for(timeout=3000)
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
                source=source or SOURCE,
                gender=gender or "women",
                lot_id=lot_id,
            )

            if product_details:
                product_name = product_details.get("name")
                domain = "https://www.jcpenney.com"
                brand = (
                    product_details.get("brand").get("name")
                    if product_details.get("brand")
                    else None
                )

                description = (
                    product_details.get("meta").get("description")
                    if product_details.get("meta")
                    else None
                )
                product_url = (
                    domain + product_details.get("meta").get("canonicalUrl")
                    if product_details.get("meta")
                    else None
                )
                category = (
                    product_details.get("category").get("name")
                    if product_details.get("category")
                    else None
                )
                rating = (
                    product_details.get("valuation").get("rating")
                    if product_details.get("valuation")
                    else None
                )
                reviews = (
                    product_details.get("valuation").get("reviews")
                    if product_details.get("valuation")
                    else None
                )
                review_count = reviews.get("count") if reviews else None

                category_breadcrumbs = product_details.get("breadCrumbInfo", {}).get(
                    "breadcrumbs", []
                )
                breadcrumbs = "/".join(
                    [
                        label.get("breadCrumbLabel")
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
                    url_item.get("url")
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
                            product.update(dict(attributes=attributes))

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
                                    product.update(dict(color=color, size=size))

            save_product_data(product)
            log.info(f"已经保存产品数据 {product_id=}")

            await page.wait_for_timeout(2000)
            # 点击 Review button
            review_button = page.locator("button#BVSummaryReviewBtn")
            await review_button.wait_for(timeout=1000)
            if review_button:
                if need_review:
                    await review_button.click()
                    log.info("点击查看评论按钮完成")
                    await page.wait_for_timeout(8000)

            await route_event.wait()
            await page.wait_for_timeout(3000)
            log.info(f"评论抓取完成 {product_id=}")
            log.info(f"关闭页面 {product_id=}")
        except TimeoutError:
            pass
        except PlaywrightTimeoutError:
            # logger.error(f"{url=} PlaywrightTimeoutError")
            pass
        except Exception as e:
            logger.error(f"{url=} {e}")
        finally:
            await page.close()


def parse_review_from_api(data: dict) -> tuple[list, int]:
    """解析评论数据"""
    total_count = data.get("TotalResults", 0)
    reviews = data.get("Results", [])
    parsed_reviews = []
    for review in reviews:
        parsed_review = dict(
            review_id=review.get("Id", None),  # review_id
            proudct_name=review.get("OriginalProductName", None),
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
            source=SOURCE,
        )
        parsed_reviews.append(parsed_review)
    # TODO 修改成异步处理 保存评论
    save_review_data(parsed_reviews)
    return parsed_reviews, total_count


async def fetch_reviews(semaphore, url, headers):
    """获取评论数据"""
    async with semaphore:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()  # 检查HTTP请求是否成功
            json_dict = response.json()
            return parse_review_from_api(json_dict)[0]


async def main():
    start = time.perf_counter()
    # 从清理后的数据获取结果
    for f in Path("projects/jcpenney/clean_data").glob("wome*.json"):
        with open(f) as file:
            log.info("-" * 50)
            log.info(f"开始处理: {f}")
            urls = json.load(file)
            await run(urls)
    log.info(f"耗时{time.perf_counter() - start}")


if __name__ == "__main__":
    asyncio.run(main())
