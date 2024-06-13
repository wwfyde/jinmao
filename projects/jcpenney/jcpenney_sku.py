import asyncio
import json
import logging

import httpx
from lxml import etree
from playwright.async_api import Playwright, async_playwright, BrowserContext, Route, Response

from crawler.config import settings
from crawler.store import save_review_data, save_product_data

PLAYWRIGHT_TIMEOUT = settings.playwright.timeout
print(f"{PLAYWRIGHT_TIMEOUT=}")
log = logging.getLogger()


async def run(playwright: Playwright) -> None:
    # 从playwright对象中获取chromium浏览器
    chromium = playwright.chromium
    user_data_dir = settings.user_data_dir
    if settings.save_login_state:
        context = await playwright.chromium.launch_persistent_context(
            user_data_dir,
            headless=False,
            # headless=False,
            slow_mo=50,  # 每个操作的延迟时间（毫秒），便于调试
            args=["--start-maximized"],  # 启动时最大化窗口
            ignore_https_errors=True,  # 忽略HTTPS错误
            devtools=True,
        )
    else:
        browser = await chromium.launch(headless=True, devtools=True)
        context = await browser.new_context()

    # 设置全局超时
    context.set_default_timeout(PLAYWRIGHT_TIMEOUT)
    # 并发打开新的页面
    # semaphore = asyncio.Semaphore(settings.playwright.concurrency or 10)
    # tasks = []
    # for i in range(10):
    #     tasks.append(open_pdp_page(context, semaphore))
    # pages = await asyncio.gather(*tasks)
    semaphore = asyncio.Semaphore(settings.playwright.concurrency or 10)

    source = "jcpenney"
    gender = "women"
    url = "https://www.jcpenney.com/p/st-johns-bay-womens-v-neck-short-sleeve-t-shirt/ppr5008403017?pTmplType=regular"
    url = "https://www.jcpenney.com/p/st-johns-bay-sleeveless-scalloped-embroidered-a-line-dress/ppr5008444125?pTmplType=regular"

    sku_id = await open_pdp_page(context, semaphore, url=url, source=source, gender=gender)
    print(sku_id)


async def open_pdp_page(
    context: BrowserContext, semaphore: asyncio.Semaphore, url: str, source: str = "jcpenney", gender: str = None
):
    async with semaphore:
        page = await context.new_page()
        page.set_default_timeout(PLAYWRIGHT_TIMEOUT)
        async with page:
            route_event = asyncio.Event()

            async def handle_route(route: Route):
                request = route.request
                if "reviews.json" in request.url:
                    print(f"{request.url=}")
                    response = await route.fetch()
                    reviews_dict = await response.json()
                    reviews, total_count = parse_review_from_api(reviews_dict)
                    log.info(f"预期评论数{total_count}, {len(reviews)}")
                    page_size = 100
                    total_pages = (total_count + page_size - 1) // page_size
                    log.info(f"总页数{total_pages}")
                    semaphore = asyncio.Semaphore(5)  # 设置并发请求数限制为5
                    tasks = []
                    for i in range(1, total_pages + 1):
                        review_url = str(
                            httpx.URL(request.url)
                            .copy_set_param("limit", page_size)
                            .copy_set_param("offset", 8 + (i - 1) * page_size)
                        )
                        tasks.append(fetch_reviews(semaphore, review_url, request.headers))

                    new_reviews = await asyncio.gather(*tasks)
                    for review in new_reviews:
                        reviews.extend(review)

                    log.info(f"实际评论数{len(reviews)}, {reviews=}")
                    log.info("设置等待事件, 等待事件被正确执行")
                    route_event.set()
                await route.continue_()

            async def handle_response(response: Response):
                if "https://api.bazaarvoice.com/data/reviews.json" in response.url and response.status == 200:
                    reviews = await response.json()
                    print(f"{reviews=}")

            await page.route("**/api.bazaarvoice.com/data/**", handle_route)
            page.on("response", handle_response)
            product_id = httpx.URL(url).path.split("/")[-1]
            await page.goto(
                url=url,
                timeout=PLAYWRIGHT_TIMEOUT,
                wait_until="load",
            )
            # 单击review按钮以加载评论
            log.info("等待评论按钮出现")
            # 等待页面加载完成
            await page.wait_for_load_state()

            preloaded_state: dict = await page.evaluate("""() => {
                                                        return window.__PRELOADED_STATE__;
                                                    }""")
            sku_id = (
                preloaded_state.get("queryParams").get("selectedSKUId") if preloaded_state.get("queryParams") else None
            )

            with open(f"productDetails_{product_id}.json", "w", encoding="utf-8") as f:
                f.write(json.dumps(preloaded_state, indent=4, ensure_ascii=False))
            # json.dumps(preloaded_state, indent=4, ensure_ascii=False)
            # TODO 保存产品详情
            product_details = preloaded_state.get("productDetails")
            product: dict = dict(
                product_id=product_id,
                sku_id=sku_id,
                source=source or "jcpenney",
                gender=gender or "women",
            )
            if product_details:
                product_name = product_details.get("name")
                domain = "https://www.jcpenney.com"
                brand = product_details.get("brand").get("name") if product_details.get("brand") else None

                description = product_details.get("meta").get("description") if product_details.get("meta") else None
                product_url = (
                    domain + product_details.get("meta").get("canonicalUrl") if product_details.get("meta") else None
                )
                category = product_details.get("category").get("name") if product_details.get("category") else None
                rating = product_details.get("valuation").get("rating") if product_details.get("valuation") else None
                reviews = product_details.get("valuation").get("reviews") if product_details.get("valuation") else None
                review_count = reviews.get("count") if reviews else None

                product.update(
                    dict(
                        product_name=product_name,
                        brand=brand,
                        description=description,
                        product_url=product_url,
                        category=category,
                        rating=rating,
                        review_count=review_count,
                    )
                )
                lots: list = product_details.get("lots", [])
                for lot in lots:
                    items = lot.get("items", [])
                    for item in items:
                        if item.get("id") == sku_id:
                            print(f"{item=}")
                            # description= item.get("description", [])
                            attributes = []
                            raw_attributes = lot.get("bulletedAttributes", [])
                            for raw_attribute in raw_attributes:
                                attributes.append(raw_attribute.get("description"))
                            if attributes:
                                product.update(dict(attributes=attributes))

                            option_values = item.get("optionValues", [])
                            for option_value in option_values:
                                if option_value.get("name") == "size":
                                    size = option_value.get("value")
                                    product.update(dict(size=size))
                                if option_value.get("name") == "color":
                                    color = option_value.get("value")
                                    product.update(dict(color=color))
                                    image_url = (
                                        option_value.get("productImage").get("url")
                                        if option_value.get("productImage")
                                        else None
                                    )
                                    product.update(dict(image_url=image_url))
                                    model_image_url = image_url
                                    product.update(dict(model_image_url=model_image_url))
                                    model_image_urls = []
                                    for alt_image in option_value.get("altImages", []):
                                        if alt_image.get("url"):
                                            model_image_urls.append(alt_image.get("url"))
                                    product.update(dict(model_image_urls=model_image_urls))
            # TODO 保存product信息
            print(product)
            # await page.pause()
            save_product_data(product)

            # TODO 保存SKU信息
            await page.pause()
            # [FIXME] 获取dom
            content = await page.content()
            tree = etree.HTML(content)
            button_node = tree.xpath('//*[@id="productOptionsColorList"]/li/div/div/button')

            print(f"{button_node=}")
            # for button in button_node:
            # print(button.text_content)
            # button_xpath = tree.getpath(button_node[0])
            # print(f"{button_xpath=}")

            buttons = page.locator('//*[@id="productOptionsColorList"]/li/div/div/button')
            button_count = await buttons.count()
            print(button_count)
            if button_count > 19:
                # 舍弃多余的对象
                log.warning("按钮数量大于19, 舍弃多余的对象")
                button_count = 19
            for i in range(button_count):
                await buttons.nth(i).click()
                await page.wait_for_load_state(timeout=10000)
                await page.wait_for_timeout(3000)
                text = await buttons.nth(i).text_content()
                sku_id = await page.locator(
                    '//*[@id="contentContainer"]/section/section[3]/div[2]/div[1]/div[1]/span'
                ).text_content()
                print(f"{sku_id=}")

                print(i, text)
            print("点击按钮完成")
            # await page.pause()
            # [FIXME] 获取评论
            await page.wait_for_selector("#accordion-button-0")
            await page.locator("#accordion-button-0").click()
            log.info("点击评论按钮")
            # await page.locator("#accordion-button-0").click()
            await page.wait_for_load_state("load", timeout=60000)
            await route_event.wait()
            log.info("等待事件被正确执行")

            print("页面加载完成")
            pass
            # await page.pause()
        return sku_id


# async def open_pdp_page(context: BrowserContext, semaphore: asyncio.Semaphore, product_id: str, sku_id: str):
#     async with semaphore:
#         page = await context.new_page()
#         page.set_default_timeout(PLAYWRIGHT_TIMEOUT)
#         async with page:
#             preloaded_state: dict = await page.evaluate("""() => {
#                                             return window.__PRELOADED_STATE__;
#                                         }""")
#             print(preloaded_state.get("productDetails"))
#
#         return sku_id


def parse_review_from_api(data: dict) -> tuple[list, int]:
    total_count = data.get("TotalResults", 0)
    reviews = data.get("Results", [])
    parsed_reviews = []
    for review in reviews:
        prased_review = dict(
            review_id=review.get("Id", None),  # review_id
            proudct_name=review.get("OriginalProductName", None),
            title=review.get("Title", None),
            comment=review.get("ReviewText", None),
            nickname=review.get("UserNickname", None),
            product_id=review.get("ProductId", None),
            # sku_id=review.get("product_variant", None) if review.get("details") else None,
            sku_id=None,  # TODO 该平台的评论没有sku_id
            helpful_votes=review.get("TotalPositiveFeedbackCount", 0),  # 点赞, 正面反馈数
            not_helpful_votes=review.get("TotalNegativeFeedbackCount", 0),  # 点踩, 负面反馈数
            rating=review.get("Rating", None),
            released_at=review.get("firstActivationDate", None),
            helpful_score=None,
            source="jcpenney",
        )
        parsed_reviews.append(prased_review)
    # 保存评论
    save_review_data(parsed_reviews)
    return parsed_reviews, total_count


def parse_dom(content: str):
    """
    解析DOM
    """


async def fetch_reviews(semaphore, url, headers):
    async with semaphore:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()  # 检查HTTP请求是否成功
            json_dict = response.json()
            return parse_review_from_api(json_dict)[0]


async def main():
    async with async_playwright() as p:
        await run(p)


if __name__ == "__main__":
    asyncio.run(main())
