import asyncio
import json
import uuid

import httpx
import structlog
from lxml import etree
from playwright.async_api import Playwright, async_playwright, Route

log = structlog.get_logger()


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
        base_url: str = "https://www.gap.com/browse/product.do?pid=793202002&vid=1&searchText=coat#pdp-page-content"
        base_url: str = "https://www.gap.com/browse/product.do?pid=470963012&cid=1127944&pcid=1127944&vid=1&grid=pds_140_948_2&cpos=444&cexp=2859&kcid=CategoryIDs%3D1127944&ctype=Listing&cpid=res24052700881663268842577#pdp-page-content"
        base_url: str = "https://www.gap.com/browse/product.do?pid=223627262&cid=1127944&pcid=1127944&vid=1&grid=pds_68_948_2&cpos=372&cexp=2859&kcid=CategoryIDs%3D1127944&ctype=Listing&cpid=res24052700881663268842577#pdp-page-content"

        async def handle_route(route: Route):
            log.info(f"拦截请求 {route.request.url}")
            request = route.request
            if "/reviews" in request.url:
                response = await route.fetch()
                json_dict = await response.json()
                # TODO  获取评论信息
                reviews, total_count = parse_reviews_from_api(json_dict)
                log.info(f"预期评论数{total_count}")
                log.info(f"预期评论数{total_count}, reviews: , {len(reviews)}")
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
                    tasks.append(fetch_reviews(semaphore, review_url, request.headers))

                new_reviews = await asyncio.gather(*tasks)
                for review in new_reviews:
                    reviews.extend(review)

                log.info(f"实际评论数{len(reviews)}")

                with open("review.json", "w") as f:
                    f.write(json.dumps(reviews))

                # log.info("获取评论信息")
                # with open(f"{settings.project_dir.joinpath('data', 'product_info')}/data-.json", "w") as f:
                #     f.write(json.dumps(json_dict))
                # pass
            # if "api" in request.pdp_url or "service" in request.pdp_url:
            #
            #     log.info(f"API Request URL: {request.pdp_url}")
            await route.continue_()

        await page.route("**/display.powerreviews.com/**", handle_route)
        # 导航到指定的URL
        await page.goto(base_url, timeout=1000 * 60 * 10)
        # 其他操作...
        # 暂停执行
        # await page.pause()
        await page.wait_for_timeout(30000)
        await page.wait_for_load_state("load")  # 等待页面加载

        # await page.wait_for_timeout(1000)
        # await page.pause()
        sku_id = httpx.URL(base_url).params.get("pid", "0")
        log.info(sku_id)

        content = await page.content()
        tree = etree.HTML(content)
        # product_name = tree.xpath('//*[@id="buy-box"]/div/h1/text()')[0]
        t = tree.xpath('//*[@id="buy-box"]/div/h1/h1/text()')
        log.info(f"{t}, {type(t)}")

        product_name = tree.xpath('//*[@id="buy-box"]/div/h1/text()')[0]
        product_name = product_name.replace("|", "")
        product_name = product_name.replace('"', "")
        log.info(product_name)
        price = tree.xpath('//*[@id="buy-box"]/div/div/div[1]/div[1]/span/text()')[0]
        original_price = tree.xpath("//*[@id='buy-box']/div/div/div[1]/div[1]/div/span/text()")[0]
        product_name = tree.xpath('//*[@id="buy-box"]/div/h1/text()')[0]

        log.info(price)
        color = tree.xpath('//*[@id="swatch-label--Color"]/span[2]/text()')[0]
        log.info(color)
        # fit_size 适合人群
        fit_and_size = tree.xpath(
            "//*[@id='buy-box-wrapper-id']/div/div[2]/div/div/div/div[2]/div[1]/div/div[1]/div/div/ul/li/text()"
        )
        log.info(fit_and_size)
        # 产品详情
        product_details: list = tree.xpath(
            '//*[@id="buy-box-wrapper-id"]/div/div[2]/div/div/div/div[2]/div[2]/div/div[1]/div/ul/li/span/text()'
        )
        log.info(f"产品详情: {product_details}")
        detail_locator = page.get_by_role("button", name="product details")
        # '//*[@id="buy-box-wrapper-id"]/div/div[2]/div/div/div/div[2]/div[2]/div/div[1]/div/ul'
        # 面料
        fabric_and_care: list = tree.xpath(
            "//*[@id='buy-box-wrapper-id']/div/div[2]/div/div/div/div[2]/div[3]/div/div[1]/div/ul/li/span/text()"
        )
        product_name = tree.xpath('//*[@id="buy-box"]/div/h1/text()')[0]
        product_id = product_details[-1]
        log.info(fabric_and_care)
        model_image_urls = tree.xpath("//*[@id='product']/div[1]/div[1]/div[3]/div[2]/div/div/div/a/@href")
        log.info(model_image_urls)
        base_url = "https://www.gap.com"
        image_tasks = []
        semaphore = asyncio.Semaphore(10)  # 设置并发请求数限制为5
        for url in model_image_urls:
            image_tasks.append(fetch_images(semaphore, base_url + url, {}))

        await asyncio.gather(*image_tasks)

        # model_image_urls = tree.xpath("//*[@id='product']/div[1]/div[1]/div[3]/div[2]/div/div[9]/div/a/href()")

        #  下载图片

        await page.pause()
        log.info(
            dict(
                price=price,
                original_price=original_price,
                product_name=product_name,
                color=color,
                fit_size=fit_and_size,
                product_details=product_details,
                fabric_and_care=fabric_and_care,
                product_id=product_id,
                model_image_urls=model_image_urls,
            )
        )
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


async def parse_sku_from_dom_content(content: str):
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
    fit_and_size = tree.xpath(
        "//*[@id='buy-box-wrapper-id']/div/div[2]/div/div/div/div[2]/div[1]/div/div[1]/div/div/ul/li/text()"
    )
    log.info(fit_and_size)
    # 产品详情
    product_details: list = tree.xpath(
        '//*[@id="buy-box-wrapper-id"]/div/div[2]/div/div/div/div[2]/div[2]/div/div[1]/div/ul/li/span/text()'
    )
    log.info(product_details)
    # 面料
    fabric_and_care: list = tree.xpath(
        "//*[@id='buy-box-wrapper-id']/div/div[2]/div/div/div/div[2]/div[3]/div/div[1]/div/ul/li/span/text()"
    )
    log.info(fabric_and_care)
    # TODO  下载 模特图片

    model_image_urls = tree.xpath("//*[@id='product']/div[1]/div[1]/div[3]/div[2]/div/div/div/a/@href")
    product_id = product_details[-1] if product_details else None
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


# 这是脚本的入口点。
# 它开始执行main函数。
if __name__ == "__main__":
    # 指定代理
    # os.environ["http_proxy"] = "http://127.0.0.1:23457"
    # os.environ["https_proxy"] = "http://127.0.0.1:23457"
    # os.environ["all_proxy"] = "socks5://127.0.0.1:23457"
    asyncio.run(main(), debug=True)
