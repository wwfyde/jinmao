import asyncio
import os
from concurrent.futures import ProcessPoolExecutor

import httpx
import redis.asyncio as redis
from fake_useragent import UserAgent
from playwright.async_api import Playwright, async_playwright, Route, Page

from crawler.config import settings
from crawler.deps import get_logger

log = get_logger("target")

source = "target"
domain = "https://www.target.com"
PLAYWRIGHT_TIMEOUT = settings.playwright.timeout
PLAYWRIGHT_TIMEOUT = 1000 * 60 * 5
PLAYWRIGHT_CONCURRENCY = settings.playwright.concurrency
PLAYWRIGHT_CONCURRENCY = 9
PLAYWRIGHT_HEADLESS: bool = settings.playwright.headless
PLAYWRIGHT_HEADLESS: bool = True

settings.save_login_state = False
# TODO  设置是否下载图片
should_download_image = False
should_get_review = True
should_get_product = True
force_get_product = False
should_use_proxy = False
if should_get_product:
    PLAYWRIGHT_CONCURRENCY = 3
if not should_download_image:
    log.warning("当前图片未设置为允许下载")

ua = UserAgent(browsers=["edge", "chrome", "safari"], platforms=["pc"], os=["windows", "macos"])


async def get_current_ip(page: Page):
    return await page.evaluate(
        "async () => { const response = await fetch('https://api.ipify.org?format=json'); const data = await response.json(); return data.ip; }"
    )


async def run(playwright: Playwright, url_info: tuple) -> None:
    # 从playwright对象中获取chromium浏览器
    chromium = playwright.chromium
    # 指定代理
    # proxy = {"server": "http://127.0.0.1:7890"}
    # 启动chromium浏览器，开启开发者工具，非无头模式
    # browser = await chromium.launch(headless=False, devtools=True)
    if should_use_proxy:
        proxy = {
            "server": settings.proxy_pool.server,
            "username": settings.proxy_pool.username,
            "password": settings.proxy_pool.password,
        }
    else:
        proxy = None
    print(f"使用代理: {proxy}")
    user_data_dir = settings.user_data_dir
    if settings.save_login_state:
        context = await playwright.chromium.launch_persistent_context(
            user_data_dir,
            headless=PLAYWRIGHT_HEADLESS,
            user_agent=ua.random,
            proxy=proxy,
            # viewport={"width": 1920, "height": 1080},
            # headless=False,
            # slow_mo=50,  # 每个操作的延迟时间（毫秒），便于调试
            # args=["--start-maximized"],  # 启动时最大化窗口
            # ignore_https_errors=True,  # 忽略HTTPS错误
            # devtools=True,  # 打开开发者工具
        )
        await context.clear_cookies()  # 清理缓存, 避免429
        await context.clear_permissions()
    else:
        pass
        browser = await chromium.launch(
            headless=PLAYWRIGHT_HEADLESS,
            proxy=proxy,
            # devtools=True,
        )
        context = await browser.new_context(
            user_agent=ua.random,
        )

    # 设置全局超时
    context.set_default_timeout(settings.playwright.timeout)
    # context.set_default_timeout(60000)
    # 创建一个新的浏览器上下文，设置视口大小
    # context = await browser.new_context(viewport={"width": 1920, "height": 1080})
    # 在浏览器上下文中打开一个新页面

    # 打开新的页面
    # 主类别, 子类别, 颜色, 尺码, url

    # 迭代类别urls
    primary_category, sub_category, color, size, base_url = url_info
    log.info(f"正在抓取{primary_category=}, {sub_category=}")
    r = redis.from_url(settings.redis_dsn, decode_responses=True, protocol=3)
    key = f"product_status:{source}:{primary_category}:{sub_category}:{color}:{size}"
    async with r:
        status = await r.get(key)
        if status == "done":
            log.warning(f"类别{primary_category=}, {sub_category=}, {color=}, {size=}商品索引已建立")
            product_urls = await r.smembers(f"target_index:{source}:{primary_category}:{sub_category}")
            log.info("商品索引已建立,从索引获取商品")
            log.info(f"类别{primary_category=}, {sub_category=}, {color=}, {size=}商品数量: {len(product_urls)}")
        else:
            agent = False
            # user_agent = ua.random
            # context = await browser.new_context(user_agent=user_agent)
            # context = await browser.new_context()
            # log.info(f"当前UserAgent: {user_agent}")
            page = await context.new_page()
            async with page:
                # 拦截所有图片
                # await page.route(
                #     "**/*",
                #     lambda route: route.abort() if route.request.resource_type == "image" else route.continue_(),
                # )
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
                        metadata, product_urls = await parse_plp_api_by_category(data=json_dict)
                        total_results = metadata.get("total_results", 0)
                        count = metadata.get("count", 0)
                        total_pages = metadata.get("total_pages", 0)
                        tasks = []
                        semaphore = asyncio.Semaphore(5)  # 设置并发请求数限制为5
                        nonlocal product_status
                        product_status = "done"
                        log.debug(f"当前类别或品牌总页数: {total_pages}, 总商品数: {total_results}")
                        if total_pages > 1:
                            for i in range(1, total_pages):
                                product_page_url = httpx.URL(request.url).copy_set_param("offset", count * i)
                                tasks.append(
                                    fetch_products(
                                        semaphore=semaphore, url=product_page_url, headers=request.headers
                                    )
                                )
                            extra_product_urls_tuple = await asyncio.gather(*tasks, return_exceptions=True)
                            product_status = "done"
                            if len(extra_product_urls_tuple) == 0:
                                log.error("未获取到商品列表, 请尝试更换IP")
                                product_status = "failed"
                            for extra_product_url in extra_product_urls_tuple:
                                if isinstance(extra_product_url, Exception):
                                    log.error(f"获取额外页面失败: {extra_product_url}")
                                    product_status = "failed"
                                elif extra_product_url:
                                    product_urls.extend(extra_product_url)
                                else:
                                    product_status = "failed"
                                    log.warning("部分页面获取失败")

                        else:
                            log.debug("当前类别或品牌只有1页, 无需额外页面抓取")
                        log.info(f"预期商品数{total_results}, 实际商品数:{len(product_urls)}")
                        if len(product_urls) == 0:
                            product_status = "failed"
                        key = f"product_status:{source}:{primary_category}:{sub_category}:{color}:{size}"

                        async with r:
                            await r.set(key, product_status)
                            log.info(f"当前商品列表{primary_category=}, {key}, 标记redis状态为: {product_status}")
                        r = redis.from_url(settings.redis_dsn, decode_responses=True, protocol=3)
                        # 将商品加入商品索引中
                        async with r:
                            print(await r.get("a"))
                            redis_key = f"target_index:{source}:{primary_category}:{sub_category}"
                            print(redis_key)

                            result = await r.sadd(redis_key, *product_urls) if product_urls else None
                            print(result)
                        plp_event.set()
                    await route.continue_()

                await page.route("**/redsky.target.com/**", handle_plp_route)

                await page.goto(base_url)
                log.info(f"进入类别页面: {base_url=}")

                await page.wait_for_timeout(3000)
                await page.wait_for_load_state(timeout=60000)
                # scroll_pause_time = random.randrange(500, 2500, 200)
                # await page.wait_for_timeout(1000)
                # await scroll_page(page, scroll_pause_time=scroll_pause_time, step=2)
                # await page.pause()
                try:
                    # 设置超时时间为5秒
                    await asyncio.wait_for(plp_event.wait(), timeout=60 * 10)
                except asyncio.TimeoutError:
                    print("等待超时")

                # 获取所有商品
                r = redis.from_url(settings.redis_dsn, decode_responses=True, protocol=3)
                async with r:
                    if product_urls:
                        insert_numbers = await r.sadd(
                            f"{source}:{primary_category}:{sub_category}:{color}", *product_urls
                        )
                        log.info(f"添加{insert_numbers}条数据到redis中")
                    else:
                        log.error(f"当前页面未获取到商品, 需要尝试切换IP, {base_url=}")

                    log.debug(f"当前类别: {primary_category=}, {sub_category=}, {len(product_urls)}")
        return product_urls


async def parse_plp_api_by_category(data: dict) -> tuple[dict, list]:
    """
    解析商品列表页API
    
    """
    products: list[dict] = data.get("data", {}).get("search", {}).get("products", [])
    if not products:
        log.error("获取产品信息失败!")
        return {}, []
    metadata: dict = data.get("data", {}).get("search", {}).get("search_response", {}).get("metadata", {})
    product_urls = []

    for product in products:
        sku_id = product.get("tcin")
        parent = product.get("parent", {})
        if parent:
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
        else:
            product_id = product.get("tcin")
            sku_url = product.get("item", {}).get("enrichment", {}).get("buy_url")
            product_base_url = product.get("item", {}).get("enrichment", {}).get("buy_url", "")
            log.warning(f"未找到父级商品信息, {sku_id=}, {product_base_url=}")

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
    log.debug(f"解析到{len(product_urls)}件商品")

    return metadata, product_urls


async def fetch_products(semaphore, url, headers):
    """
    通过Category等PLP页面获取商品列表
    """
    async with semaphore:
        try:
            log.debug(f"请求额外类别页面: {url}")
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.get(url, headers=headers)
                log.debug(f"请求状态码: {response.status_code}")
                response.raise_for_status()  # 检查HTTP请求是否成功
                json_dict = response.json()
                await asyncio.sleep(5)
                return (await parse_plp_api_by_category(json_dict))[-1]
        except Exception as exc:
            log.error(f"请求额外页面失败, {exc=}, {exc.args=}")
            return []


async def run_playwright_instance(url_info):
    # 创建一个playwright对象并将其传递给run函数
    retry_times = 0
    while retry_times < 1:
        try:
            async with async_playwright() as p:
                await run(p, url_info)
                ...
        except Exception as exc:
            log.error(f"执行失败: {exc}")
        retry_times += 1
        log.warning(f"尝试重试: {retry_times}")

        await asyncio.sleep(5)


async def main():
    loop = asyncio.get_running_loop()
    num_processes = os.cpu_count() // 2
    num_processes = 2
    urls = []

    women_urls = [
        # ("women", "maternity", "default", "default",
        #  "https://www.target.com/c/maternity-clothing-women/-/N-5ouvi"),  # 
        # ("women", "graphic-tees", "default", "batch1",
        #  "https://www.target.com/c/graphic-tees-sweatshirts-women-s-clothing/-/N-4y2xwZ4u9pjZqama8Z4u9goZ5xeljZcv1blcqhq3mZ5y70kZfo87bqov5agZrg0dh?type=products&moveTo=product-list-grid"),
        # ("women", "graphic-tees", "default", "batch2",
        #  "https://www.target.com/c/graphic-tees-sweatshirts-women-s-clothing/-/N-4y2xwZ5xeljZvef8a?type=products&moveTo=product-list-grid"),
        # ("women", "graphic-tees", "default", "batch3",
        #  "https://www.target.com/c/graphic-tees-sweatshirts-women-s-clothing/-/N-4y2xwZcv1blcs3gscZvef8a?type=products&moveTo=product-list-grid"),
        # ("women", "graphic-tees", "default", "batch4",
        #  "https://www.target.com/c/graphic-tees-sweatshirts-women-s-clothing/-/N-4y2xwZ4u9ldZ5y24gZ5y1h6Z5y2kw?type=products&moveTo=product-list-grid"),
        # ("women", "graphic-tees", "pop-culture", "black",
        #  "https://www.target.com/c/graphic-tees-sweatshirts-women-s-clothing/-/N-4y2xwZvef8aZcv1blczeafkZ5y761?type=products&moveTo=product-list-grid"),
        # ("women", "graphic-tees", "pop-culture", "gray",
        #  "https://www.target.com/c/graphic-tees-sweatshirts-women-s-clothing/-/N-4y2xwZvef8aZcv1blczeafkZ5y759?type=products&moveTo=product-list-grid"),

        # 
        # ("women", "jumpsuits-rompers", "default", "default",
        #  "https://www.target.com/c/jumpsuits-rompers-women-s-clothing/-/N-4y52e"),  # 抓取完成

        # ("women","socks-hosiery","default","default","https://www.target.com/c/socks-hosiery-women-s-clothing/-/N-5xtbdZ600jqZgfdyb?moveTo=product-list-grid"),  # win
        # ("women","socks-hosiery","default","extra", "https://www.target.com/c/socks-hosiery-women-s-clothing/-/N-5xtbdZq8ldyZ1ktcxZ68721?moveTo=product-list-grid"),  # win

        # (
        #     "women",
        #     "intimates",
        #     "default",
        #     "default",
        #     "https://www.target.com/c/intimates-women-s-clothing/-/N-5xtcfZ5y34t",
        # ),  # 已完成

        # (
        #     "women",
        #     "t-shirts",
        #     "black",
        #     "M",
        #     "https://www.target.com/c/t-shirts-women-s-clothing/-/N-9qjryZvef8aZ5y761?moveTo=product-list-grid",
        # ),  # 完成
        # (
        #     "women",
        #     "t-shirts",
        #     "batch1",
        #     "M",
        #     "https://www.target.com/c/t-shirts-women-s-clothing/-/N-9qjryZvef8aZ5y6q6Z5y746Z5y70hZ5y67t?moveTo=product-list-grid"
        # ),  # 完成
        # (
        #     "women",
        #     "t-shirts",
        #     "batch2",
        #     "M",
        #     "https://www.target.com/c/t-shirts-women-s-clothing/-/N-9qjryZvef8aZ5y73rZ5xr7iZ5y759?moveTo=product-list-grid"
        # ),  # 完成
        # (
        #     "women",
        #     "t-shirts",
        #     "batch3",
        #     "M",
        #     "https://www.target.com/c/t-shirts-women-s-clothing/-/N-9qjryZvef8aZ55iviZ5xrh3Z5y76nZ5y6hb?moveTo=product-list-grid"
        # ),  # 完成
        # (
        #     "women",
        #     "t-shirts",
        #     "batch4",
        #     "M",
        #     "https://www.target.com/c/t-shirts-women-s-clothing/-/N-9qjryZvef8aZ55iviZ5xrh3Z5y76nZ5y6hb?moveTo=product-list-grid"
        # ),  # 完成(
        # (
        #     "women",
        #     "t-shirts",
        #     "batch5",
        #     "M",
        #     "https://www.target.com/c/t-shirts-women-s-clothing/-/N-9qjryZvef8aZ5y76dZ5y713Z5y750Z5y72c?moveTo=product-list-grid"
        # ),  # 完成

        # ("women", "dresses", "black", "M", "https://www.target.com/c/dresses-women-s-clothing/-/N-5xtcgZvef8aZ5y761"),  # 完成
        # (
        #     "women",
        #     "pajama-sets",
        #     "default",
        #     "default",
        #     "https://www.target.com/c/pajama-sets-pajamas-loungewear-women-s-clothing/-/N-5xtbz",
        # ),  # 完成
        # (
        #     "women",
        #     "pajama-tops",
        #     "default",
        #     "default",
        #     "https://www.target.com/c/pajama-tops-pajamas-loungewear-women-s-clothing/-/N-5xtby",
        # ),  # 抓取中 采用三级类别
        # (
        #     "women",
        #     "pajama-bottoms",
        #     "default",
        #     "default",
        #     "https://www.target.com/c/pajama-bottoms-pajamas-loungewear-women-s-clothing/-/N-5xtc2",
        # ),  # 抓取中 采用三级类别
        # (
        #     "women",
        #     "coats-jackets",
        #     "default",
        #     "default",
        #     "https://www.target.com/c/coats-jackets-women-s-clothing/-/N-5xtchZ66rho?moveTo=product-list-grid",
        # ),  # 完成
        # (
        #     "women",
        #     "coats-jackets",
        #     "default",
        #     "extra",
        #     "https://www.target.com/c/coats-jackets-women-s-clothing/-/N-5xtchZech2s2krbvfZech2s25o21uZech2s2c5qdaZech2s25tn8bZech2s2bgfyq?moveTo=product-list-grid",
        # ),  # win
        # (
        #     "women",
        #     "bottoms",
        #     "black",
        #     "M",
        #     "https://www.target.com/c/bottoms-women-s-clothing/-/N-txhdtZ5y761Zvef8a",
        # ),  # 完成
        # (
        #     "women",
        #     "bottoms",
        #     "multi",
        #     "M",
        #     "https://www.target.com/c/bottoms-women-s-clothing/-/N-txhdtZvef8aZ5y6q6Z5y70hZ5y746Z5y67tZ5y759Z5y73rZ5xr7iZ5xrh3Z55iviZ5y76nZ5y6hbZ5y76dZ5y713Z5y750Z5y72c?moveTo=product-list-grid",
        # ),  # 完成

        # (
        #     "women",
        #     "activewear",
        #     "default",
        #     "default",
        #     "https://www.target.com/c/activewear-women-s-clothing/-/N-5xtcl",
        # ),  # win 抓取完毕
        # (
        #     "women",
        #     "swimsuits",
        #     "black",
        #     "M",
        #     "https://www.target.com/c/swimsuits-women-s-clothing/-/N-5xtbwZ5y34tZ5y761?moveTo=product-list-grid",
        # ),  # 抓取完毕
        # ("women", "jeans", "black", "M", "https://www.target.com/c/jeans-women-s-clothing/-/N-5xtc8Z5y761Zvef8a?moveTo=product-list-grid",),  # noqa # 已完成
        # ("women", "jeans", "default", "default", "https://www.target.com/c/jeans-women-s-clothing/-/N-5xtc8",),  # 已完成
        # noqa # 已完成
        ("women", "shorts", "default", "default",
         "https://www.target.com/c/shorts-women-s-clothing/-/N-5xtc5"),  # 已完成
    ]
    # urls.extend(women_urls)
    men_urls = [
        # (
        #     "men",
        #     "pants",
        #     "default",
        #     "default",
        #     "https://www.target.com/c/pants-men-s-clothing/-/N-5xu29",
        # ),  # 完成
        # (
        #     "men",
        #     "shorts",
        #     "default",
        #     "default",
        #     "https://www.target.com/c/shorts-men-s-clothing/-/N-5xu27",
        # ),
        # (
        #     "men",
        #     "swimsuits",
        #     "default",
        #     "default",
        #     "https://www.target.com/c/swimsuits-men-s-clothing/-/N-5xu1y",
        # ),
        # (
        #     "men",
        #     "jeans",
        #     "default",
        #     "default",
        #     "https://www.target.com/c/jeans-men-s-clothing/-/N-5xu2b",
        # ),
        # (
        #     "men",
        #     "activewear",
        #     "default",
        #     "default",
        #     "https://www.target.com/c/activewear-men-s-clothing/-/N-5xu2e",
        # ),
        # (
        #     "men",
        #     "jackets-coats",
        #     "default",
        #     "default",
        #     "https://www.target.com/c/jackets-coats-men-s-clothing/-/N-5xu2a",
        # ),
        # (
        #     "men",
        #     "sleepwear-pajamas-robes",
        #     "black",
        #     "default",
        #     "https://www.target.com/c/sleepwear-pajamas-robes-men-s-clothing/-/N-5xu26Zgup4zc5zk7s?moveTo=product-list-grid",
        # ),
        # (
        #     "men",
        #     "sleepwear-pajamas-robes",
        #     "batch1",
        #     "default",
        #     "https://www.target.com/c/sleepwear-pajamas-robes-men-s-clothing/-/N-5xu26Zgup4zc5xkwhZgup4zc5xku0Zgup4zc5xktoZgup4zc5xkumZgup4zc5xktmZgup4zc5xkunZgup4zc5xkw9?moveTo=product-list-grid",
        # ),
        # (
        #     "men",
        #     "sleepwear-pajamas-robes",
        #     "batch2",
        #     "default",
        #     "https://www.target.com/c/sleepwear-pajamas-robes-men-s-clothing/-/N-5xu26Zgup4zc5xkerZesftkZgup4zc5xkwkZgup4zc5xkugZgup4zc5xkvlZgup4zc5zk8tZgup4zc5xkwvZgup4zc5xkpk?moveTo=product-list-grid",
        # ),

        # (
        #     "men",
        #     "socks",
        #     "batch1",
        #     "default",
        #     "https://www.target.com/c/socks-men-s-clothing/-/N-5xu21Zgup4zc5zkqbZgup4zc5xkwhZgup4zc5xku0Zgup4zc5xktoZgup4zc5xkumZgup4zc5zk7sZgup4zc5xktmZgup4zc5xkun?moveTo=product-list-grid",
        # ),
        # (
        #     "men",
        #     "socks",
        #     "batch2",
        #     "default",
        #     "https://www.target.com/c/socks-men-s-clothing/-/N-5xu21Zgup4zc5xkw9?moveTo=product-list-grid",
        # ),
        # (
        #     "men",
        #     "socks",
        #     "batch3",
        #     "default",
        #     "https://www.target.com/c/socks-men-s-clothing/-/N-5xu21Zgup4zc5xkerZesftkZgup4zc5xkwkZgup4zc5xkugZgup4zc5xkvlZgup4zc5zk8tZgup4zc5xkwvZgup4zc5xkpk?moveTo=product-list-grid",
        # ),

        # (
        #     "men",
        #     "underwear",
        #     "default",
        #     "default",
        #     "https://www.target.com/c/underwear-men-s-clothing/-/N-4vr7v",
        # ),
        # (
        #     "men",
        #     "undershirts",
        #     "default",
        #     "default",
        #     "https://www.target.com/c/undershirts-men-s-clothing/-/N-4vr7u",
        # ),
        # (
        #     "men",
        #     "suits",
        #     "default",
        #     "default",
        #     "https://www.target.com/c/suits-men-s-clothing/-/N-5xu20",
        # ),
        # (
        #     "men",
        #     "shoes",
        #     "batch1",
        #     "default",
        #     "https://www.target.com/c/men-s-shoes/-/N-5xu1wZgup4zc5zk7s?moveTo=product-list-grid",
        # ),
        # (
        #     "men",
        #     "shoes",
        #     "batch2",
        #     "default",
        #     "https://www.target.com/c/men-s-shoes/-/N-5xu1wZgup4zc5zkqbZgup4zc5xku0Zgup4zc5xktoZgup4zc5xktmZgup4zc5xkun?moveTo=product-list-grid",
        # ),
        # (
        #     "men",
        #     "shoes",
        #     "batch3",
        #     "default",
        #     "https://www.target.com/c/men-s-shoes/-/N-5xu1wZgup4zc5xkumZgup4zc5xkwhZgup4zc5xkw9Zgup4zc5xkerZesftkZgup4zc5xkwkZgup4zc5xkugZgup4zc5xkvlZgup4zc5zk8tZgup4zc5xkwvZgup4zc5xkpk?moveTo=product-list-grid",
        # ),
        # TODO 大量 https://www.target.com/c/graphic-tees-t-shirts-men-s-clothing/-/N-55cxi
        # (
        #     "men",
        #     "sweaters",
        #     "default",
        #     "default",
        #     "https://www.target.com/c/sweaters-men-s-clothing/-/N-5xu1z",
        # ),
        # (
        #     "men",
        #     "polo-shirts",
        #     "default",
        #     "default",
        #     "https://www.target.com/c/polo-shirts-men-s-clothing/-/N-55cxg",
        # ),
        # (
        #     "men",
        #     "dress-shirts",
        #     "default",
        #     "default",
        #     "https://www.target.com/c/dress-shirts-men-s-clothing/-/N-37dl1",
        # ),
        # (
        #     "men",
        #     "casual-button-downs-shirts",
        #     "default",
        #     "default",
        #     "https://www.target.com/c/casual-button-downs-shirts-men-s-clothing/-/N-55cxe",
        # ),
        # # 按type + color 分类 然后集合
        # (
        #     "men",
        #     "t-shirts-tank-tops",
        #     "black",
        #     "medium",
        #     "https://www.target.com/c/t-shirts-tank-tops-men-s-clothing/-/N-4ujkzZgup4zc5zk7sZ5y34tZyshar?moveTo=product-list-grid",
        # ),
        # (
        #     "men",
        #     "t-shirts-tank-tops",
        #     "batch1",
        #     "default",
        #     "https://www.target.com/c/t-shirts-tank-tops-men-s-clothing/-/N-4ujkzZysharZgup4zc5xku0Zgup4zc5xktoZgup4zc5xktmZgup4zc5xkun?moveTo=product-list-grid",
        # ),
        # (
        #     "men",
        #     "t-shirts-tank-tops",
        #     "gray",
        #     "default",
        #     "https://www.target.com/c/t-shirts-tank-tops-men-s-clothing/-/N-4ujkzZysharZgup4zc5xkum?moveTo=product-list-grid",
        # ),
        # (
        #     "men",
        #     "t-shirts-tank-tops",
        #     "batch2",
        #     "default",
        #     "https://www.target.com/c/t-shirts-tank-tops-men-s-clothing/-/N-4ujkzZysharZgup4zc5xkw9Zgup4zc5xkugZgup4zc5xkwhZgup4zc5xkerZesftkZgup4zc5xkwkZgup4zc5xkvlZgup4zc5zk8tZgup4zc5xkwvZgup4zc5xkpk?moveTo=product-list-grid",
        # ),
        # (
        #     "men",
        #     "t-shirts-tank-tops",
        #     "type1",
        #     "default",
        #     "https://www.target.com/c/t-shirts-tank-tops-men-s-clothing/-/N-4ujkzZ3zu90Z8vd6xZyk58tZ8r6cnZxjnrxZ4r9n4Z329yuZl99ueZ6mtooZ6n8y3Zal25lfve9g3Zfg86zZd6tkuZal25lfljjs7Zh85adZbkzaeZngyq0?moveTo=product-list-grid",
        # ),
        # (
        #     "men",
        #     "t-shirts-tank-tops",
        #     "tank-tops",
        #     "default",
        #     "https://www.target.com/c/t-shirts-tank-tops-men-s-clothing/-/N-4ujkzZt0hxy?moveTo=product-list-grid",
        # ),

        # TODO TopsSweatshirts & Hoodies  https://www.target.com/c/hoodies-sweatshirts-men-s-clothing/-/N-551v0?moveTo=product-list-grid
        # 
        # (
        #     "men",
        #     "hoodies-sweatshirts",
        #     "blue",
        #     "default",
        #     "https://www.target.com/c/hoodies-sweatshirts-men-s-clothing/-/N-551v0Zgup4zc5xku0?moveTo=product-list-grid",
        # ),
        # (
        #     "men",
        #     "hoodies-sweatshirts",
        #     "batch1",
        #     "default",
        #     "https://www.target.com/c/hoodies-sweatshirts-men-s-clothing/-/N-551v0Zgup4zc5zkqbZgup4zc5xkw9Zgup4zc5xkugZgup4zc5xkwhZgup4zc5xktoZgup4zc5xkerZesftkZgup4zc5xktmZgup4zc5xkunZgup4zc5xkwkZgup4zc5xkvl?moveTo=product-list-grid",
        # ), (
        #     "men",
        #     "hoodies-sweatshirts",
        #     "batch2",
        #     "default",
        #     "https://www.target.com/c/hoodies-sweatshirts-men-s-clothing/-/N-551v0Zgup4zc5xkpkZgup4zc5xkwvZgup4zc5zk8t?moveTo=product-list-grid",
        # ), (
        #     "men",
        #     "hoodies-sweatshirts",
        #     "gray",
        #     "default",
        #     "https://www.target.com/c/hoodies-sweatshirts-men-s-clothing/-/N-551v0Zgup4zc5xkum?moveTo=product-list-grid",
        # ),
        # (
        #     "men",
        #     "hoodies-sweatshirts",
        #     "black",
        #     "default",
        #     "https://www.target.com/c/hoodies-sweatshirts-men-s-clothing/-/N-551v0Zgup4zc5zk7s?moveTo=product-list-grid",
        # ),

        # TODO Graphic Tees & Sweatshirts https://www.target.com/c/graphic-tees-t-shirts-men-s-clothing/-/N-55cxi
        # (
        #     "men",
        #     "graphic-tees-t-shirts",
        #     "father-s-day",
        #     "default",
        #     "https://www.target.com/c/graphic-tees-t-shirts-men-s-clothing/father-s-day/-/N-55cxiZ8zw2q",
        # ),
        # (
        #     "men",
        #     "graphic-tees-t-shirts",
        #     "americana",
        #     "default",
        #     "https://www.target.com/c/graphic-tees-t-shirts-men-s-clothing/americana/-/N-55cxiZgejlf",
        # ),
        # (
        #     "men",
        #     "graphic-tees-t-shirts",
        #     "pop-culture",
        #     "batch1",
        #     "https://www.target.com/c/graphic-tees-t-shirts-men-s-clothing/-/N-55cxiZgup4zc5xktmZiv1xsZmr8zmZrhi27Zgup4zc5xku0Zgup4zc5xkunZgup4zc5xkto?moveTo=product-list-grid",
        # ),
        # (
        #     "men",
        #     "graphic-tees-t-shirts",
        #     "pop-culture",
        #     "black",
        #     "https://www.target.com/c/graphic-tees-t-shirts-men-s-clothing/-/N-55cxiZiv1xsZmr8zmZrhi27Zgup4zc5zk7s?moveTo=product-list-grid",
        # ),
        # (
        #     "men",
        #     "graphic-tees-t-shirts",
        #     "pop-culture",
        #     "batch2",
        #     "https://www.target.com/c/graphic-tees-t-shirts-men-s-clothing/-/N-55cxiZgup4zc5xkumZiv1xsZmr8zmZrhi27Zgup4zc5xkwhZgup4zc5xkw9?moveTo=product-list-grid",
        # ),
        # (
        #     "men",
        #     "graphic-tees-t-shirts",
        #     "pop-culture",
        #     "batch3",
        #     "https://www.target.com/c/graphic-tees-t-shirts-men-s-clothing/-/N-55cxiZiv1xsZmr8zmZrhi27ZesftkZgup4zc5xkwkZgup4zc5xkugZgup4zc5xkvlZgup4zc5zk8tZgup4zc5xkpkZgup4zc5xkwv?moveTo=product-list-grid",
        # ),
        # (
        #     "men",
        #     "graphic-tees-t-shirts",
        #     "music",
        #     "default",
        #     "https://www.target.com/c/graphic-tees-t-shirts-men-s-clothing/music/-/N-55cxiZj7oro",
        # ),
        (
            "men",
            "graphic-tees-t-shirts",
            "tv-and-movie",
            "batch1",
            "https://www.target.com/c/graphic-tees-t-shirts-men-s-clothing/-/N-55cxiZfo87bqov5agZrg0dhZgup4zc5xktm?type=products&moveTo=product-list-grid",
        ),
        (
            "men",
            "graphic-tees-t-shirts",
            "tv-and-movie",
            "batch2",
            "https://www.target.com/c/graphic-tees-t-shirts-men-s-clothing/-/N-55cxiZfo87bqov5agZrg0dhZgup4zc5zk7s?type=products&moveTo=product-list-grid",
        ),
        (
            "men",
            "graphic-tees-t-shirts",
            "tv-and-movie",
            "batch3",
            "https://www.target.com/c/graphic-tees-t-shirts-men-s-clothing/-/N-55cxiZfo87bqov5agZrg0dhZgup4zc5xku0?type=products&moveTo=product-list-grid",
        ),
        (
            "men",
            "graphic-tees-t-shirts",
            "tv-and-movie",
            "batch4",
            "https://www.target.com/c/graphic-tees-t-shirts-men-s-clothing/-/N-55cxiZgup4zc5zkqbZgup4zc5xktoZgup4zc5xkunZfo87bqov5agZrg0dhZgup4zc5xkum?type=products&moveTo=product-list-grid",
        ), (
            "men",
            "graphic-tees-t-shirts",
            "tv-and-movie",
            "batch5",
            "https://www.target.com/c/graphic-tees-t-shirts-men-s-clothing/-/N-55cxiZfo87bqov5agZrg0dhZgup4zc5xkwhZgup4zc5xkw9ZesftkZgup4zc5xkwkZgup4zc5xkugZgup4zc5xkvl?type=products&moveTo=product-list-grid",
        ), (
            "men",
            "graphic-tees-t-shirts",
            "tv-and-movie",
            "batch6",
            "https://www.target.com/c/graphic-tees-t-shirts-men-s-clothing/-/N-55cxiZfo87bqov5agZrg0dhZgup4zc5zk8tZgup4zc5xkwvZgup4zc5xkpk?type=products&moveTo=product-list-grid",
        ),

    ]
    # urls.extend(men_urls)
    pet_urls = [
        # ("pets", "dog-supplies", "batch1", "unknown",
        #  "https://www.target.com/c/dog-supplies-pets/-/N-5xt3tZ6q8fqiw8pkZ4yl67?moveTo=product-list-grid"),
        # ("pets", "dog-supplies", "batch2", "unknown",
        #  "https://www.target.com/c/dog-supplies-pets/-/N-5xt3tZ4yl4tZ4yl59Z4yl4i?moveTo=product-list-grid"),
        # ("pets", "dog-supplies", "batch3", "unknown",
        #  "https://www.target.com/c/dog-supplies-pets/-/N-5xt3tZe3sjevcc90xZe3sjevyxi6xZ2nsb6Z4yl7mZ4yjup?moveTo=product-list-grid"
        #  ),
        # ("pets", "dog-supplies", "batch4", "unknown",
        #  "https://www.target.com/c/dog-supplies-pets/-/N-5xt3tZw1fi5Z4yl7mZe3sjev7pshl?moveTo=product-list-grid"
        #  ),
        # ("pets", "dog-supplies", "batch5", "unknown",
        #  "https://www.target.com/c/dog-supplies-pets/-/N-5xt3tZ4yl7m?moveTo=product-list-grid"
        #  ),
        # ("pets", "cat-supplies", "batch2", "unknown",
        #  "https://www.target.com/c/cat-supplies-pets/-/N-5xt42Z6q8fqiw8pkZ4yl67Z4yl4tZ4yl59Z4yl4i?moveTo=product-list-grid"
        #  ),
        # ("pets", "cat-supplies", "batch3", "unknown",
        #  "https://www.target.com/c/cat-supplies-pets/-/N-5xt42Z4yl7m?moveTo=product-list-grid"
        #  ),
        # ("pets", "gifts-for-pets", "batch1", "unknown",
        #  "https://www.target.com/c/gifts-for-pets/-/N-55z1mZ5n5og?moveTo=product-list-grid"
        #  ),
        # 
        # ("pets", "gifts-for-pets", "batch2", "unknown",
        #  "https://www.target.com/c/gifts-for-pets/-/N-55z1mZ5n5p5?moveTo=product-list-grid"
        #  ),
        # ("pets", "gifts-for-pets", "batch3", "unknown",
        #  "https://www.target.com/c/gifts-for-pets/-/N-55z1mZzebtaZ4ycp2Z5n4heZ1pthuZ5n4hgZ55k79Z5n4hdZ9fm9hZsqpmwnp13q0Z5n5ofZ5n5k1Zsqpmwnqs6mxZ5n4o7?moveTo=product-list-grid"
        #  ),
        # ("pets", "dog-food", "default", "unknown",
        #  "https://www.target.com/c/dog-food-supplies-pets/-/N-5xt3m"
        #  ),
        ("pets", "cat-food", "default", "unknown",
         "https://www.target.com/c/cat-food-supplies-pets/-/N-5xt3y"
         ),
        ("pets", "cat-litter", "default", "unknown",
         "https://www.target.com/c/cat-litter-supplies-pets/-/N-5xt3v"
         ),
        ("pets", "cat-toys", "default", "unknown",
         "https://www.target.com/c/cat-toys-supplies-pets/-/N-5xt3u"
         ),
        ("pets", "cat-treats", "default", "unknown",
         "https://www.target.com/c/cat-treats-supplies-pets/-/N-bpteb"
         ),
    ]
    # urls.extend(pet_urls)
    bed_urls = [
        ("furniture", "beds", "black", "default",
         "https://www.target.com/c/beds-bedroom-furniture/-/N-4ym22Z5y761?moveTo=product-list-grid"),
        ("furniture", "beds", "gray", "default",
         "https://www.target.com/c/beds-bedroom-furniture/-/N-4ym22Z5y759?moveTo=product-list-grid"),
        ("furniture", "beds", "brown", "default",
         "https://www.target.com/c/beds-bedroom-furniture/-/N-4ym22Z5y746?moveTo=product-list-grid"),
        ("furniture", "beds", "white", "default",
         "https://www.target.com/c/beds-bedroom-furniture/-/N-4ym22Z5y750?moveTo=product-list-grid"),
        ("furniture", "beds", "misc1", "default",
         "https://www.target.com/c/beds-bedroom-furniture/-/N-4ym22Z5y70hZ5y6q6Z5y6nd?moveTo=product-list-grid"),
        ("furniture", "beds", "misc2", "default",
         "https://www.target.com/c/beds-bedroom-furniture/-/N-4ym22Z5y73rZ5xr7iZ5y76dZ5y713Z55iviZ5xrh3Z5y76nZ5y67tZ5y6hbZ5y72c?moveTo=product-list-grid"),
    ]  # 索引建立完成 deprecated, 不再需要抓取
    # urls.extend(bed_urls)
    kids_urls = [
        # ("girls", "girls-uniforms", "default", "default",
        #  "https://www.target.com/c/girls-uniforms-school-kids/-/N-55q4q"),  # noinspection
        # ("girls", "tops", "gray", "default",
        #  "https://www.target.com/c/tops-girls-clothing-kids/-/N-5xtvuZgup4zc5zkqbZgup4zc5xktoZgup4zc5xktmZgup4zc5xkum?moveTo=product-list-grid"),
        # # noinspection
        # ("girls", "tops", "black", "default",
        #  "https://www.target.com/c/tops-girls-clothing-kids/-/N-5xtvuZgup4zc5zk7s?moveTo=product-list-grid"),  # partial
        # ("girls", "tops", "blue", "default",
        #  "https://www.target.com/c/tops-girls-clothing-kids/-/N-5xtvuZgup4zc5xku0?moveTo=product-list-grid"),  # partial
        # ("girls", "tops", "green", "default",
        #  "https://www.target.com/c/tops-girls-clothing-kids/-/N-5xtvuZgup4zc5xkwh?moveTo=product-list-grid"),
        # ("girls", "tops", "batch", "default",
        #  "https://www.target.com/c/tops-girls-clothing-kids/-/N-5xtvuZgup4zc5xkw9Zgup4zc5xkpkZgup4zc5xkerZgup4zc5zk8tZesftk?moveTo=product-list-grid"),
        # ("girls", "tops", "pink", "default",
        #  "https://www.target.com/c/tops-girls-clothing-kids/-/N-5xtvuZgup4zc5xkwk?moveTo=product-list-grid"),
        # ("girls", "tops", "purple", "default",
        #  "https://www.target.com/c/tops-girls-clothing-kids/-/N-5xtvuZgup4zc5xkug?moveTo=product-list-grid"),
        # ("girls", "tops", "purple", "default",
        #  "https://www.target.com/c/tops-girls-clothing-kids/-/N-5xtvuZgup4zc5xkug?moveTo=product-list-grid"),
        # ("girls", "tops", "red", "default",
        #  "https://www.target.com/c/tops-girls-clothing-kids/-/N-5xtvuZgup4zc5xkvl?moveTo=product-list-grid"),
        # ("girls", "tops", "red", "default",
        #  "https://www.target.com/c/tops-girls-clothing-kids/-/N-5xtvuZgup4zc5xkvl?moveTo=product-list-grid"),
        # ("girls", "tops", "white", "default",
        #  "https://www.target.com/c/tops-girls-clothing-kids/-/N-5xtvuZgup4zc5xkwv?moveTo=product-list-grid"),
        ("girls", "bottoms", "default", "default",
         "https://www.target.com/c/bottoms-girls-clothing-kids/-/N-5xtw6"),
        ("girls", "dresses-rompers", "default", "default",
         "https://www.target.com/c/dresses-rompers-girls-clothing-kids/-/N-5xtvz"),
        ("girls", "pajamas-robes", "default", "default",
         "https://www.target.com/c/pajamas-robes-girls-clothing-kids/-/N-5xtvx"),
        ("girls", "swimsuits", "default", "default",
         "https://www.target.com/c/swimsuits-girls-clothing-kids/-/N-5xtvv"),
        ("girls", "coats-jackets", "default", "default",
         "https://www.target.com/c/coats-jackets-girls-clothing-kids/-/N-5xtvy"),
        ("girls", "girls-accessories", "default", "default",
         "https://www.target.com/c/girls-accessories-kids/-/N-5xtwl"),
        ("girls", "socks-tights", "default", "default",
         "https://www.target.com/c/socks-tights-girls-clothing-kids/-/N-5xtvw"),
        ("girls", "underwear-bras", "default", "default",
         "https://www.target.com/c/underwear-bras-girls-clothing-kids/-/N-5xtvp"),
        ("girls", "activewear", "default", "default",
         "https://www.target.com/c/activewear-girls-clothing-kids/-/N-5xtw9"),
        ("girls", "multipacks", "default", "default",
         "https://www.target.com/c/girls-multipacks/-/N-4a9wj"),
        ("girls", "new-arrivals", "default", "default",
         "https://www.target.com/c/girls-new-arrivals/-/N-n9klq"),
        ("girls", "shoes", "default", "default",
         "https://www.target.com/c/girls-shoes/-/N-5xtvo"),
        ("girls", "adaptive-clothing", "default", "default",
         "https://www.target.com/c/girls-adaptive-clothing-kids/-/N-8b31p"),
        ("girls", "outfit-sets", "default", "default",
         "https://www.target.com/c/outfit-sets-girls-clothing-kids-shoes-accessories/-/N-55yiu"),
        ("girls", "all-in-motion", "default", "default",
         "https://www.target.com/c/all-in-motion-girls/-/N-rhwq0"),

        # TODO  Girls’ Character Clothing https://www.target.com/c/girls-character-clothing/-/N-4u9ul

        ("boys", "boys-uniforms", "default", "default",
         "https://www.target.com/c/boys-uniforms-school-kids/-/N-55q4r"),
        ("boys", "tween-boys", "default", "default",
         "https://www.target.com/c/tween-boys-clothing/-/N-2ldf3"),
        ("boys", "bottoms", "default", "default",
         "https://www.target.com/c/bottoms-boys-clothing-kids/-/N-5xty0"),
        ("boys", "dresswear", "default", "default",
         "https://www.target.com/c/dresswear-boys-clothing-kids/-/N-5xtxw"),

    ]
    urls.extend(kids_urls)
    with ProcessPoolExecutor(max_workers=num_processes) as executor:
        tasks = [loop.run_in_executor(executor, async_runner, url_info) for url_info in urls]

        results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in results:
            if isinstance(result, Exception):
                log.error(f"Task resulted in an exception: {result}")
            else:
                log.info(result)


# 这是脚本的入口点。
# 它开始执行main函数。
def async_runner(url_info):
    # 指定本地代理
    asyncio.run(run_playwright_instance(url_info))


if __name__ == '__main__':
    asyncio.run(main())
