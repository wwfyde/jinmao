import asyncio
import uuid

import httpx
from lxml import etree
from playwright.async_api import Playwright, async_playwright

from crawler import log


async def run(playwright: Playwright) -> None:
    # 从playwright对象中获取chromium浏览器
    chromium = playwright.chromium
    browser = await chromium.launch(headless=True)
    context = await browser.new_context()

    # 设置全局超时
    # context.set_default_timeout(settings.playwright.timeout)
    context.set_default_timeout(1000 * 60 * 10)
    # 创建一个新的浏览器上下文，设置视口大小
    # context = await browser.new_context(viewport={"width": 1920, "height": 1080})
    # 在浏览器上下文中打开一个新页面

    page = await context.new_page()
    page.set_default_timeout(1000 * 60 * 5 * 2)
    async with page:
        # 拦截所有图像
        await page.route(
            "**/*",
            lambda route: route.abort() if route.request.resource_type == "image" else route.continue_(),
        )

        # TODO 指定url
        base_url: str = "https://www.gap.com/browse/category.do?cid=14417#pageId=0&department=48"

        # 导航到指定的URL
        await page.goto(base_url, timeout=1000 * 60 * 10)
        # 其他操作...
        # 暂停执行
        # await page.pause()
        # await page.wait_for_timeout(30000)
        # await page.wait_for_load_state()  # 等待页面加载

        await page.wait_for_timeout(5000)
        # await page.pause()

        content = await page.content()
        tree = etree.HTML(content)
        pdp_urls = tree.xpath("//*[@id='faceted-grid']/section/div/div/div/div[1]/a/@href")
        log.info(f"商品数: {len(pdp_urls)} 商品链接: {pdp_urls}")

        # model_image_urls = tree.xpath("//*[@id='product']/div[1]/div[1]/div[3]/div[2]/div/div[9]/div/a/href()")

        #  下载图片

        await page.pause()

    # 关闭浏览器context
    # TODO 暂不关闭浏览器
    await context.close()


async def fetch_reviews(semaphore, url, headers):
    async with semaphore:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()  # 检查HTTP请求是否成功
            json_dict = response.json()
            return parse_reviews_from_api(json_dict)[0]


async def fetch_images(semaphore, url, headers):
    async with semaphore:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()  # 检查HTTP请求是否成功
            image_bytes = response.content
            with open(f"{str(uuid.uuid4())}.jpg", "wb") as f:
                f.write(image_bytes)


async def main():
    # 创建一个playwright对象并将其传递给run函数
    async with async_playwright() as p:
        await run(p)
        ...


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


def parse_reviews_from_api_old(r: dict) -> tuple[list[dict], int | None]:
    # 获取分页信息
    log.info("开始解析评论数据")
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


# 这是脚本的入口点。
# 它开始执行main函数。
if __name__ == "__main__":
    # 指定代理
    # os.environ["http_proxy"] = "http://127.0.0.1:23457"
    # os.environ["https_proxy"] = "http://127.0.0.1:23457"
    # os.environ["all_proxy"] = "socks5://127.0.0.1:23457"
    asyncio.run(main(), debug=True)
