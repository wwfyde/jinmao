import asyncio
import logging

import httpx
import redis.asyncio as redis
from fake_useragent import UserAgent
from playwright.async_api import Playwright, async_playwright, Route

from crawler.config import settings
from projects.gap.gap import PLAYWRIGHT_HEADLESS
from projects.target.target_category_concurrency import open_pdp_page
from projects.target import log

# 增加按品牌搜索
base_api_url = "https://redsky.target.com/redsky_aggregations/v1/web/plp_search_v2?key=9f36aeafbe60771e321a7cc95a78140772ab3e96&brand_id=mg0o7&channel=WEB&count=24&default_purchasability_filter=true&include_dmc_dmr=true&new_search=true&offset=0&page=%2Fb%2Fmg0o7&platform=desktop&pricing_store_id=2407&spellcheck=true&store_ids=2407%2C2037%2C1180%2C2108%2C1078&useragent=Mozilla%2F5.0+%28Macintosh%3B+Intel+Mac+OS+X+10_15_7%29+AppleWebKit%2F537.36+%28KHTML%2C+like+Gecko%29+Chrome%2F126.0.0.0+Safari%2F537.36&visitor_id=018FC7FE1AAB0201847FB0C6772CA3B5&zip=24520"

source = "target"
domain = "https://www.target.com"
PLAYWRIGHT_TIMEOUT = settings.playwright.timeout
PLAYWRIGHT_CONCURRENCY = settings.playwright.concurrency
PLAYWRIGHT_CONCURRENCY = 9
settings.save_login_state = False
download_image = False

from crawler.config import settings

log_libraries = ["httpx", "httpcore", "openai"]
for library in log_libraries:
    library_logger = logging.getLogger(library)
    library_logger.setLevel(logging.WARN)

ua = UserAgent(browsers=["edge", "chrome", "safari"])


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
    brand_id = "gk29m"
    plp_api = "https://redsky.target.com/redsky_aggregations/v1/web/plp_search_v2"
    urls = [
        # ("stars-above", "https://www.target.com/b/stars-above/-/N-g0mql"),
        ("auden", "https://www.target.com/b/auden/-/N-mg0o7"),
        # ("colsie", "https://www.target.com/b/colsie/-/N-gk29m"),
    ]
    # 迭代类别urls
    for index, (brand, base_url) in enumerate(urls):
        r = redis.from_url(settings.redis_dsn, decode_responses=True, protocol=3)
        key = f"product_status_brand:{source}:{brand}"
        async with r:
            status = await r.get(key)
            if status == "done":
                log.info(f"当前{brand}, {key}, 标记redis状态为:{status}, 从redis中获取")

                product_urls = await r.smembers(f"target_brand:{source}:{brand}")
                log.info(f"当前{brand}, 从redis中获取{len(product_urls)}条数据")

            else:
                agent = False
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
                    product_urls: list[str] = []
                    product_status: str = "done"
                    plp_event = asyncio.Event()

                    async def handle_plp_route(route: Route):
                        r = redis.from_url(settings.redis_dsn, decode_responses=True, protocol=3)
                        request = route.request
                        if "plp_search_v2" in request.url:
                            log.info(f"拦截产品列表页成功: {request.url}")
                            response = await route.fetch()
                            json_dict = await response.json()
                            nonlocal product_urls
                            metadata, product_urls = await parse_plp_api(data=json_dict)
                            total_results = metadata.get("total_results", 0)
                            count = metadata.get("count", 0)
                            total_pages = metadata.get("total_pages", 0)
                            tasks = []
                            semaphore = asyncio.Semaphore(5)  # 设置并发请求数限制为5
                            nonlocal product_status
                            product_status = "done"
                            if total_pages > 1:
                                for i in range(1, total_pages):
                                    product_page_url = httpx.URL(request.url).copy_set_param("offset", count * i)
                                    tasks.append(
                                        fetch_products(
                                            semaphore=semaphore, url=product_page_url, headers=request.headers
                                        )
                                    )
                                extra_product_urls_tuple = await asyncio.gather(*tasks)
                                product_status = "done"
                                for extra_product_url in extra_product_urls_tuple:
                                    if extra_product_url:
                                        product_urls.extend(extra_product_url)
                                    else:
                                        product_status = "failed"
                                        log.warning("部分页面获取失败")

                            else:
                                log.debug("当前类别或品牌只有1页, 无需额外页面抓取")
                            log.info(f"预期商品数{total_results}, 实际商品数:{len(product_urls)}")
                            key = f"product_status_brand:{source}:{brand}"

                            async with r:
                                await r.set(key, product_status)
                                log.info(f"当前{brand}, {key}, 标记redis状态为: {product_status}")

                            plp_event.set()
                        await route.continue_()

                    await page.route("**/redsky.target.com/**", handle_plp_route)

                    await page.goto(base_url)
                    log.info(f"进入类别页面: {base_url=}")

                    await page.wait_for_load_state(timeout=60000)
                    # await page.wait_for_load_state("networkidle")
                    await page.wait_for_timeout(3000)
                    # scroll_pause_time = random.randrange(500, 2500, 200)
                    # await page.wait_for_timeout(1000)
                    # await scroll_page(page, scroll_pause_time=scroll_pause_time, step=3)
                    # await page.pause()

                    # 获取所有商品
                    await plp_event.wait()
                    r = redis.from_url(settings.redis_dsn, decode_responses=True, protocol=3)
                    async with r:
                        if product_urls:
                            insert_numbers = await r.sadd(f"target_brand:{source}:{brand}", *product_urls)
                            log.info(f"添加{insert_numbers}条数据到redis中")
                        else:
                            log.error(f"当前页面未获取到商品, 需要尝试切换IP, {base_url=}")

                        log.debug(f"{product_urls}, {len(product_urls)}")

            print(f"一共获取商品数: {len(product_urls)}")
            semaphore = asyncio.Semaphore(PLAYWRIGHT_CONCURRENCY)  # 设置并发请求数限制为10

            plp_tasks = []

            for url in product_urls:
                print(url)
                url = url.replace(domain, "")
                url = domain + url
                plp_tasks.append(
                    open_pdp_page(context, url=url, semaphore=semaphore, brand=brand, source=source, task_type="brand")
                )
            results = await asyncio.gather(*plp_tasks)

            log.info(f"任务下载状态: {results}")


async def fetch_products(semaphore, url, headers):
    async with semaphore:
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()  # 检查HTTP请求是否成功
                json_dict = response.json()
                return (await parse_plp_api(json_dict))[-1]
        except Exception as exc:
            log.error(f"请求额外页面失败, {exc}")
            return []


async def parse_plp_api(data: dict) -> tuple[dict, list]:
    products: list[dict] = data.get("data", {}).get("search", {}).get("products", [])
    if not products:
        log.error("获取产品信息失败!")
        return {}, []
    metadata: dict = data.get("data", {}).get("search", {}).get("search_response", {}).get("metadata", {})
    product_urls = []

    for product in products:
        sku_id = product.get("tcin")
        parent = product.get("parent", {})
        product_id = parent.get("tcin")
        sku_url = product.get("item", {}).get("enrichment", {}).get("buy_url")
        product_base_url = parent.get("item", {}).get("enrichment", {}).get("buy_url", "")
        if product_base_url:
            product_url = product_base_url + f"?preselect={sku_id}#lnk=sametab"
            product_urls.append(product_url)
        else:
            product_url = None
        image_url = product.get("item", {}).get("enrichment", {}).get("images", {}).get("primary_image_url")
        alternate_image_urls = (
            product.get("item", {}).get("enrichment", {}).get("images", {}).get("alternate_image_urls", [])
        )
        image_urls = [image_url] + alternate_image_urls if image_url else alternate_image_urls

    return metadata, product_urls


async def main():
    # 创建一个playwright对象并将其传递给run函数
    i = 0
    while i < 3:
        i += 1
        try:
            async with async_playwright() as p:
                await run(p)
        except Exception as exc:
            log.error(f"发生异常: {exc}")
        await asyncio.sleep(15)


# 这是脚本的入口点。
# 它开始执行main函数。
if __name__ == "__main__":
    # 指定本地代理
    asyncio.run(main())
