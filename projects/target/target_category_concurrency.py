import asyncio
import os
import random
import re
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime
from mimetypes import guess_extension
from pathlib import Path
from typing import Literal

import httpx
import redis.asyncio as redis
from fake_useragent import UserAgent
from playwright.async_api import Playwright, async_playwright, Route, Page, BrowserContext

from crawler.config import settings
from crawler.deps import get_logger
from crawler.store import save_review_data_async, save_product_data_async, save_product_detail_data_async, \
    save_sku_data_async
from crawler.utils import scroll_page

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
                        semaphore = asyncio.Semaphore(1)  # 设置并发请求数限制为5
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

                    log.debug(f"{product_urls}, {len(product_urls)}")
    semaphore = asyncio.Semaphore(PLAYWRIGHT_CONCURRENCY)  # 设置并发请求数限制为10
    pdp_tasks = []
    for url in product_urls:
        url = url.replace(domain, "")
        url = domain + url
        pdp_tasks.append(
            open_pdp_page(
                # browser,
                context=context,
                url=url,
                semaphore=semaphore,
                source=source,
                primary_category=primary_category,
                sub_category=sub_category,
                color=color,
                size=size,
            )
        )
    print(f"一共获取商品数: {len(product_urls)}")

    results = await asyncio.gather(*pdp_tasks)


async def open_pdp_page(
        context: BrowserContext,
        # browser: Browser,
        *,
        url: str,
        semaphore: asyncio.Semaphore,
        source: str,
        primary_category: str | None = None,
        sub_category: str | None = None,
        color: str | None = None,
        size: str | None = None,
        brand: str | None = None,
        task_type: Literal["brand", "category"] = "category",
) -> tuple[str, str]:
    """
    打开产品详情页并
    :params:url: 产品url
    """
    async with semaphore:
        product_id = httpx.URL(url).path.split("/")[-1].split("-")[-1]
        sku_id = httpx.URL(url).params.get("preselect")
        log.info(f"通过PDP(产品详情页)URL获取商品id:{product_id=} SKU:{sku_id=}")
        if not force_get_product:
            r = redis.from_url(settings.redis_dsn, decode_responses=True, protocol=3)
            async with r:
                category_status_flag = await r.get(
                    f"status:{source}:{product_id}:{sku_id}"
                )
                brand_status_flag = await r.get(f"status_brand:{source}:{brand}:{product_id}:{sku_id}")
                # log.info(
                #     f"商品{product_id}, sku:{sku_id}, redis抓取状态标记: {category_status_flag=}, {brand_status_flag=}"
                # )
                category_review_status_key = f"review_status:{source}:{product_id}"
                brand_review_status_key = f"review_status_brand:{source}:{brand}:{product_id}"
                category_review_status_flag = await r.get(category_review_status_key)
                brand_review_status_flag = await r.get(brand_review_status_key)
                # log.info(
                #     f"{category_status_flag=}, {brand_status_flag=}, {category_review_status_flag=}, {brand_review_status_flag=}"
                # )

                # 处理跳过情形
                if (category_status_flag == "done" or brand_status_flag == "done") and not should_get_review:
                    log.warning(f"商品:{product_id=}, {sku_id},商品已抓取, 但不需要抓取评论, 跳过")
                    return product_id, sku_id
                if (category_status_flag == "done" or brand_status_flag == "done") and (
                        category_review_status_flag == "done" or brand_review_status_flag == "done"):
                    log.warning(f"商品:{product_id=}, {sku_id}, 商品和评论均已抓取过, 跳过")
                    return product_id, sku_id
                if (category_review_status_flag == "done" or brand_review_status_flag == "done") and not (
                        should_get_product or force_get_product):
                    log.warning(f"商品:{product_id=}, {sku_id},评论已抓取, 但不需要抓取商品, 跳过")
                    return product_id, sku_id
                if not should_get_product and not should_get_review:
                    log.warning(f"商品:{product_id=}, {sku_id},不需要抓取商品和评论, 跳过")
                    return product_id, sku_id
                log.info(
                    f"抓取商品或评论:{product_id=}, {sku_id},{category_status_flag=}, {category_review_status_flag=}, {brand_status_flag=}, {brand_review_status_flag=} 开始抓取")

        # user_agent = ua.random
        # log.info(f"当前UserAgent: {user_agent}")
        # context = await browser.new_context(user_agent=user_agent)
        # context = await browser.new_context()
        page = await context.new_page()
        page.set_default_timeout(PLAYWRIGHT_TIMEOUT)
        async with page:
            # 拦截所有图像
            await page.route(
                "**/*",
                lambda route: route.abort() if route.request.resource_type == "image" else route.continue_(),
            )

            # TODO 指定url

            review_status = None  # 评论抓取状态跟踪
            # product_id = None  # 从pdp页接口获取商品id
            product: dict | None = None
            sku: dict | None = None
            if should_get_product or force_get_product:
                product_event = asyncio.Event()
            if should_get_review:
                review_event = asyncio.Event()

            # skus_event = asyncio.Event()

            async def handle_review_route(route: Route):
                request = route.request
                # 等待商品接口获取到product_id 后再执行评论
                # await product_event.wait()
                # nonlocal product_id
                if "summary" in request.url:
                    r = redis.from_url(settings.redis_dsn, decode_responses=True, protocol=3)
                    async with r:
                        category_key = f"review_status:{source}:{product_id}"
                        category_review_status = await r.get(category_key)
                        log.info(f"拦截评论请求API:{route.request.url}")
                        brand_key = f"review_status_brand:{source}:{brand}:{product_id}"
                        brand_review_status = await r.get(brand_key)
                        log.info(
                            f"商品评论: {product_id} 评论, redis状态标记:{category_review_status=}, {brand_review_status=}")
                        log.info(f"拦截评论请求API:{route.request.url}")

                    if category_review_status != "done" and brand_review_status != "done":
                        response = await route.fetch()
                        json_dict = await response.json()
                        # TODO  获取评论信息
                        reviews, total_count = parse_target_review_from_api(json_dict)
                        # log.info(f"预期评论数{total_count}")
                        # log.info(f"预期评论数{total_count}, reviews: , {len(reviews)}")
                        page_size = 50
                        total_pages = (total_count + page_size - 1) // page_size
                        total_pages = total_pages if total_pages <= 50 else 50
                        log.info(f"总页数{total_pages}")

                        semaphore = asyncio.Semaphore(10)  # 设置并发请求数限制为5
                        tasks = []
                        reviews = []  # 该项目中需要清除默认8条
                        for i in range(0, total_pages):
                            review_url = (
                                httpx.URL(request.url).copy_set_param("page", i).copy_set_param("size", page_size)
                            )
                            tasks.append(fetch_reviews(semaphore, review_url, request.headers))

                        new_reviews = await asyncio.gather(*tasks)
                        nonlocal review_status
                        for review in new_reviews:
                            if review is not None:
                                reviews.extend(review)
                            else:
                                review_status = "failed"
                                log.warning(f"评论获取失败: {review}")

                        log.info(f"商品:{product_id=}, 预期评论数{total_count}, 实际评论数{len(reviews)}")

                        if review_status == "failed":
                            async with r:
                                if task_type == "category":
                                    await r.set(category_key, "failed")
                                elif task_type == "brand":
                                    await r.set(brand_key, "failed")
                        else:
                            # 保存评论到数据库
                            if len(reviews) > 0:
                                log.info("保存评论到数据库")
                                # save_review_data(reviews)
                                await save_review_data_async(reviews)
                            else:
                                pass

                            async with r:
                                log.info(f"商品评论{product_id}抓取完毕, 标记redis状态")
                                if task_type == "category":
                                    await r.set(category_key, "done")
                                elif task_type == "brand":
                                    await r.set(brand_key, "done")

                        review_event.set()
                        # with open("review.json", "w") as f:
                        #     # 使用orjson以支持datetime格式
                        #     f.write(orjson.dumps(reviews, option=orjson.OPT_NAIVE_UTC).decode("utf-8"))
                    else:
                        log.warning(
                            f"商品[{product_id=}]的评论已抓取过, 类别状态: {category_review_status}, 品牌状态: {brand_review_status}, 跳过")
                        review_event.set()
                        # log.info("获取评论信息")
                        # with open(f"{settings.project_dir.joinpath('data', 'product_info')}/data-.json", "w") as f:
                        #     f.write(json.dumps(json_dict))
                        # pass
                # if "api" in request.pdp_url or "service" in request.pdp_url:
                #
                #     log.info(f"API Request URL: {request.pdp_url}")
                await route.continue_()

            async def handle_pdp_route(route: Route):
                request = route.request
                if "pdp_client" in request.url:
                    log.info(
                        f"拦截产品详情页API: {route.request.url}",
                    )
                    # TODO 获取产品信息
                    response = await route.fetch()
                    json_dict = await response.json()
                    nonlocal product
                    nonlocal sku
                    product, sku = await parse_target_product(
                        json_dict,
                        primary_category=primary_category,
                        sub_category=sub_category,
                        source=source,
                        sku_id=sku_id,
                        product_id=product_id,
                        color=color,
                        size=size,
                        # cookies=cookies,
                        # headers=headers,
                        brand=brand,
                        task_type=task_type,
                    )
                    product_event.set()
                    log.info(f"商品详情: {product}")

                # if "pdp_variation_hierarchy" in request.url:
                #     log.info(f"拦截产品变体API: {route.request.url}")
                #     response = await route.fetch()
                #     json_dict = await response.json()
                #     skus = parse_target_product_variation(json_dict)
                #     skus_event.set()
                #     log.info(f"商品变体: {len(skus) if skus else 0}")
                await route.continue_()

            if should_get_review:
                await page.route("**/r2d2.target.com/**", handle_review_route)

            if should_get_product or force_get_product:
                await page.route("**/redsky.target.com/**", handle_pdp_route)
            # 导航到指定的URL
            # 其他操作...
            # 暂停执行
            response = await page.goto(url, timeout=PLAYWRIGHT_TIMEOUT)
            ip_info = await get_current_ip(page)
            log.debug(f"当前使用ip: {ip_info}")

            cookies_raw = await context.cookies(url)
            cookies = {cookie["name"]: cookie["value"] for cookie in cookies_raw}
            headers = response.headers

            # await page.pause()
            log.info("等待页面加载")
            await page.wait_for_timeout(3000)
            # 滚动页面以加载评论
            scroll_pause_time = random.randrange(1000, 2500, 500)
            await scroll_page(page, scroll_pause_time)
            # 通过点击按钮加载评论
            # await page.locator('//*[@id="above-the-fold-information"]/div[2]/div/div/div/div[3]/button').click()

            await page.wait_for_load_state("domcontentloaded")  # 等待页面加载
            log.info("页面加载完成")

            # 或者等待某个selector 加载完成

            # await page.wait_for_timeout(1000)
            # await page.pause()

            # DOM中解析商品属性并下载商品图片并保存

            #  优化商品属性 获取方案, 通过API 完成 deprecated
            # description, attributes = await parse_pdp_from_dom(page, sku_id=sku_id, cookies=cookies, headers=headers)
            if should_get_product or force_get_product:
                try:
                    # 设置超时时间为5秒
                    await asyncio.wait_for(product_event.wait(), timeout=60 * 1)
                except asyncio.TimeoutError:
                    log.warning("等待超时")
                log.info("PDP(产品详情页)接口执行完毕")
            # await skus_event.wait()
            if should_get_review:
                try:
                    # 设置超时时间为5秒
                    await asyncio.wait_for(review_event.wait(), timeout=60 * 5 * 6)
                except asyncio.TimeoutError:
                    log.warning("等待超时")
                log.info("Review(评论)接口执行完毕")

            # await page.pause()
            if should_get_product or force_get_product:
                if product:
                    # product.update(dict(attributes=attributes, description=description))
                    log.info(f"商品{product_id=}, {sku_id=}获取到产品信息, 保存到数据库")
                    await save_product_data_async(product)
                    await save_product_detail_data_async(product)  # 保存商品详情
                    product_status = "done"

                else:
                    product_status = "faild"
                    log.warning(f"商品{product_id=}, {sku_id=}未获取到产品信息,")
                if sku:
                    await save_sku_data_async(sku)  # 保存sku信息
                else:
                    log.warning(f"商品{product_id=}, {sku_id=}未获取到SKU信息")

                # 保存产品信息到数据库
                # await page.pause()

                # fit_size 适合人群
                r = redis.from_url(settings.redis_dsn, decode_responses=True, protocol=3)

                async with r:
                    log.info(f"商品{product_id=}, {sku_id=}抓取完毕, 标记redis状态为 {product_status}")
                    if task_type == "category":
                        await r.set(
                            f"status:{source}:{product_id}:{sku_id}", product_status
                        )
                    elif task_type == "brand":
                        await r.set(f"status_brand:{source}:{brand}:{product_id}:{sku_id}", product_status)
                if should_get_product or force_get_product:
                    log.warning("等待随机时间")
                    await asyncio.sleep(random.randint(10, 30))
            else:
                log.warning("跳过商品状态检查")
            return product_id, sku_id


async def fetch_reviews(semaphore, url, headers):
    async with semaphore:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()  # 检查HTTP请求是否成功
            json_dict = response.json()
            return parse_target_review_from_api(json_dict)[0]


async def fetch_images(
        *,
        semaphore: asyncio.Semaphore,
        url: str,
        headers: dict | None = None,
        cookies: dict | None = None,
        file_path: Path | str,
        query_params: str = "?wid=2400&hei=2400&qlt=100",
) -> bool:
    async with semaphore:
        try:
            start_time = asyncio.get_event_loop().time()
            async with httpx.AsyncClient(timeout=60) as client:
                log.debug(f"下载图片: {url}")
                response = await client.get(url + query_params, headers=headers, cookies=cookies)
                content_type = response.headers.get("Content-Type", "")
                if content_type.startswith("image"):
                    # image_basename = image_basename.split(".")[0]
                    extension = guess_extension(content_type)
                    log.info(f"图片类型{extension=}")
                else:
                    log.warning("非图片类型!")
                response.raise_for_status()  # 检查HTTP请求是否成功
                image_bytes = response.content
                with open(f"{str(file_path)}{extension}", "wb") as f:
                    f.write(image_bytes)
            end_time = asyncio.get_event_loop().time()
            log.debug(f"下载图片耗时: {end_time - start_time:.2f}s")
            return True
        except Exception as exc:
            log.error(f"下载图片失败, {exc=}")
            return False


def parse_target_review_from_api(
        data: dict, product_name: str | None = None, sku_id: str | None = None
) -> tuple[list, int]:
    reviews = data.get("reviews").get("results", []) if data.get("reviews") else []
    total_count = data.get("reviews").get("total_results", 0) if data.get("reviews") else []
    parsed_reviews = []
    # log.info(f"评论数: {len(reviews)}")
    for review in reviews:
        # log.debug(f"评论ID : {review.get('id')}")
        photos = review.get("photos", None)
        parsed_review = dict(
            review_id=review.get("id", None),  # review_id
            proudct_name=product_name,  # TODO 该平台不存在
            title=review.get("title", None)[:128] if review.get("title") else None,
            comment=review.get("text", None)[:1024] if review.get("text") else None,
            photos=photos,
            outer_photos=photos,
            nickname=review.get("author", {}).get("nickname") if review.get("author", {}) else None,
            product_id=review.get("Tcin", None),
            # sku_id=review.get("product_variant", None) if review.get("details") else None,
            sku_id=None,  # TODO 该平台的评论没有sku_id
            helpful_votes=review.get("feedback").get("helpful", None)
            if review.get("feedback")
            else None,  # 点赞, 正面反馈数
            not_helpful_votes=review.get("feedback").get("unhelpful", None)
            if review.get("feedback")
            else None,  # 点踩, 负面反馈数
            inappropriate=review.get("feedback").get("inappropriate", None)
            if review.get("feedback")
            else None,  # 不合适 target 专用
            rating=review.get("Rating", None),  # 评分
            released_at=review.get("firstActivationDate", None),
            helpful_score=None,
            source="target",
            created_at=datetime.fromisoformat(review.get("submitted_at").replace("Z", "+00:00"))
            if review.get("submitted_at")
            else None,
            updated_at=datetime.fromisoformat(review.get("modified_at").replace("Z", "+00:00"))
            if review.get("modified_at")
            else None,
        )
        parsed_reviews.append(parsed_review)
        # TODO 下载评论
        if isinstance(photos, list):
            pass
    # 将评论保持到数据库
    # save_review_data(parsed_reviews)
    return parsed_reviews, total_count


async def parse_pdp_from_dom(
        page: Page,
        *,
        cookies: dict | None = None,
        headers: dict | None = None,
        sku_id: str | None = None,
):
    # content = await page.content()
    # tree = etree.HTML(content)
    # product_name = tree.xpath('//*[@id="buy-box"]/div/h1/text()')[0]
    # product_name_locator = tree.xpath('//*[@id="buy-box"]/div/h1/h1/text()')
    # log.info(t, type(t))

    # TODO 下载图片

    product_name_locator = page.locator('//*[@id="buy-box"]/div/h1')
    if await product_name_locator.count() > 0:
        product_name = await product_name_locator.inner_text()
    else:
        product_name = None
    log.info(product_name)
    price_locator = page.locator('//*[@id="buy-box"]/div/div/div[1]/div[1]/span')
    if await price_locator.count() > 0:
        price = await price_locator.inner_text()
    else:
        price = None
    original_price_locator = page.locator("//*[@id='buy-box']/div/div/div[1]/div[1]/div/span")
    if await original_price_locator.count() > 0:
        original_price = await original_price_locator.inner_text()
    else:
        original_price = None
    log.info(f"{original_price=}")
    log.info(price)
    color_locator = page.locator("//*[@id='swatch-label--Color']/span[2]")
    if await color_locator.count() > 0:
        color = await color_locator.inner_text()
    else:
        color = None

    # 通过页面获取产品描述
    try:
        await page.get_by_role("button", name="Description").click()
    except Exception:
        log.error("点击描述按钮失败")

    description_locator = page.locator('[data-test="item-details-description"]')
    if await description_locator.count() > 0:
        description = await description_locator.inner_text()
    else:
        description = None
    print(f"{description=}")

    # TODO 通过页面获取产品属性
    try:
        await page.locator("//main/div/div[2]/div/div/div/div[3]/button").click()
        """#product-detail-tabs > div > div:nth-child(3) > button"""
        log.info("点击按钮成功")
    except Exception as exc:
        log.error(f"点击按钮失败: {exc}")
    size_locator = page.get_by_text(re.compile("Sizing: ", re.IGNORECASE))
    size = (await size_locator.first.inner_text()).split(": ")[-1] if await size_locator.count() > 0 else None
    print(f"{size=}")

    material_locator = page.get_by_text(re.compile("Material: ", re.IGNORECASE))
    material = (
        (await material_locator.first.inner_text()).split(": ")[-1] if await material_locator.count() > 0 else None
    )
    print(f"{material=}")

    garment_style_locator = page.get_by_text(re.compile("Garment Style: ", re.IGNORECASE))
    garment_style = (
        (await garment_style_locator.first.inner_text()).split(": ")[-1]
        if await garment_style_locator.count() > 0
        else ""
    )
    print(f"garment_style: {garment_style}")

    garment_length_locator = page.get_by_text(re.compile("Garment Length: ", re.IGNORECASE))
    garment_length = (
        (await garment_length_locator.first.inner_text()).split(": ")[-1]
        if await garment_length_locator.count() > 0
        else None
    )
    print(f"{garment_length=}")
    neckline_locator = page.get_by_text(re.compile("Neckline: ", re.IGNORECASE))
    neckline = (
        (await neckline_locator.first.inner_text()).split(": ")[-1] if await neckline_locator.count() > 0 else None
    )
    print(f"{neckline=}")
    fabric_name_locator = page.get_by_text(re.compile("Fabric Name: ", re.IGNORECASE))
    fabric_name = (
        (await fabric_name_locator.first.inner_text()).split(": ")[-1]
        if await fabric_name_locator.count() > 0
        else None
    )
    print(f"{fabric_name=}")

    total_garment_length_locator = page.get_by_text(re.compile("Total Garment Length: ", re.IGNORECASE))
    total_garment_length = (
        (await total_garment_length_locator.first.inner_text()).split(": ")[-1]
        if await total_garment_length_locator.count() > 0
        else None
    )
    print(f"{total_garment_length=}")

    garment_details_locator = page.get_by_text(re.compile("Garment Details: ", re.IGNORECASE))
    garment_details = (
        (await garment_details_locator.first.inner_text()).split(": ")[-1]
        if await garment_details_locator.count() > 0
        else None
    )
    print(f"{garment_details=}")

    pacage_quantity_locator = page.get_by_text(re.compile("Package Quantity: ", re.IGNORECASE))
    package_quantity = (
        (await pacage_quantity_locator.first.inner_text()).split(": ")[-1]
        if await pacage_quantity_locator.count() > 0
        else None
    )
    print(f"{package_quantity=}")

    garment_back_type_locator = page.get_by_text(re.compile("Garment Back Type: ", re.IGNORECASE))
    garment_back_type = (
        (await garment_back_type_locator.first.inner_text()).split(": ")[-1]
        if await garment_back_type_locator.count() > 0
        else None
    )
    print(f"{garment_back_type=}")

    fabric_weight_type_locator = page.get_by_text(re.compile("Fabric Weight Type: ", re.IGNORECASE))
    fabric_weight_type = (
        (await fabric_weight_type_locator.first.inner_text()).split(": ")[-1]
        if await fabric_weight_type_locator.count() > 0
        else None
    )
    print(f"{fabric_weight_type=}")

    garment_sleeve_style_locator = page.get_by_text(re.compile("Garment Sleeve Style: ", re.IGNORECASE))
    garment_sleeve_style = (
        (await garment_sleeve_style_locator.first.inner_text()).split(": ")[-1]
        if await garment_sleeve_style_locator.count() > 0
        else None
    )
    print(f"{garment_sleeve_style=}")

    care_and_cleaning_locator = page.get_by_text(re.compile("Care and Cleaning: ", re.IGNORECASE))
    care_and_cleaning = (
        (await care_and_cleaning_locator.first.inner_text()).split(": ")[-1]
        if await care_and_cleaning_locator.count() > 0
        else None
    )
    print(f"{care_and_cleaning=}")

    tcin_locator = page.get_by_text(re.compile("TCIN: ", re.IGNORECASE))
    tcin = (await tcin_locator.first.inner_text()).split(": ")[-1] if await tcin_locator.count() > 0 else None
    print(f"{tcin=}")

    upc_locator = page.get_by_text(re.compile("UPC: ", re.IGNORECASE))
    upc = (await upc_locator.first.inner_text()).split(": ")[-1] if await upc_locator.count() > 0 else None
    print(f"{upc=}")

    item_number_locator = page.get_by_text(re.compile("Item Number (DPCI): ", re.IGNORECASE))
    item_number = (
        (await item_number_locator.first.inner_text()).split(": ")[-1]
        if await item_number_locator.count() > 0
        else None
    )
    print(f"{item_number=}")

    origin_locator = page.get_by_text(re.compile("Origin: ", re.IGNORECASE))
    origin = (await origin_locator.first.inner_text()).split(": ")[-1] if await origin_locator.count() > 0 else None
    print(f"{origin=}")

    attributes = dict(
        size=size,
        material=material,
        garment_style=garment_style,
        garment_length=garment_length,
        neckline=neckline,
        fabric_name=fabric_name,
        total_garment_length=total_garment_length,
        garment_details=garment_details,
        package_quantity=package_quantity,
        garment_back_type=garment_back_type,
        fabric_weight_type=fabric_weight_type,
        garment_sleeve_style=garment_sleeve_style,
        care_and_cleaning=care_and_cleaning,
        tcin=tcin,
        upc=upc,
        item_number=item_number,
        origin=origin,
    )
    return description, attributes
    pass


async def parse_target_product(
        data: dict,
        sku_id: str | None = None,
        product_id: str | None = None,
        source: str | None = "target",
        primary_category: str | None = None,
        sub_category: str | None = None,
        color: str | None = None,
        size: str | None = None,
        headers: dict | None = None,
        cookies: dict | None = None,
        brand: str | None = None,
        task_type: Literal["brand", "category"] = "category",
) -> tuple[dict | None, dict | None]:
    """
    解析target商品信息
    """
    product: dict | None = data.get("data").get("product") if data.get("data") else {}
    if not product:
        log.error(f"未从接口中获取到商品信息,{product_id=}, {sku_id=}, {task_type=} ")
        return None, None
    product_id_from_api = product.get("tcin")
    if product_id_from_api != product_id:
        log.warning(f"从接口中获取到的{product_id_from_api=}, 与从url中获取的{product_id=}不同, 可能是同一件或类似商品")
        raise ValueError(f"严重错误! 从接口中获取到的{product_id_from_api=}, 与从url中获取的{product_id=}不同")
    category = product.get("category", {}).get("name", "")
    # product.get("category").get("parent_category_id", "") + " " + product.get("category").get("name", "")
    parent_category = product.get("category", {}).get("parent_category_id", "")
    rating = product.get("ratings_and_reviews", {}).get("statistics", {}).get("rating", {}).get("average")
    rating_count = product.get("ratings_and_reviews", {}).get("statistics", {}).get("rating", {}).get("count")
    review_count = product.get("ratings_and_reviews", {}).get("statistics", {}).get("review_count", {})
    product_url = product.get("item", {}).get("enrichment", {}).get("buy_url", {})

    children: list[dict] = product.get("children", [])
    found = False
    image_urls = []
    image_url = ""
    alternate_image_urls = []
    for child in children:
        if child.get("tcin") == sku_id:
            image_url = child.get("item", {}).get("enrichment", {}).get("images", {}).get("primary_image_url")

            alternate_image_urls = (
                child.get("item", {}).get("enrichment", {}).get("images", {}).get("alternate_image_urls", [])
            )

            image_urls = [image_url] + alternate_image_urls if image_url else alternate_image_urls
            # color =

            found = True
            break

    if not found:
        image_url = product.get("item", {}).get("enrichment", {}).get("images", {}).get("primary_image_url")

        alternate_image_urls = (
            product.get("item", {}).get("enrichment", {}).get("images", {}).get("alternate_image_urls", [])
        )

        image_urls = [image_url] + alternate_image_urls if image_url else alternate_image_urls

    if should_download_image:
        r = redis.from_url(settings.redis_dsn, decode_responses=True, protocol=3)
        async with r:
            if task_type == "category":
                image_status1 = await r.get(
                    f"image_download_status:{source}:{product_id}:{sku_id}"
                )
            elif task_type == "brand":
                image_status2 = await r.get(f"image_download_status_brand:{source}:{brand}:{product_id}:{sku_id}")
            if image_status1 == "done" or image_status2 == "done":
                log.warning(f"商品: {product_id}, sku:{sku_id}, 图片已下载, 跳过")
            else:
                image_tasks = []
                semaphore = asyncio.Semaphore(10)  # 设置并发请求数限制为10
                if task_type == "category":
                    sku_dir = settings.data_dir.joinpath(
                        source, primary_category, sub_category, str(product_id), str(sku_id)
                    )
                elif task_type == "brand":
                    sku_dir = settings.data_dir.joinpath(source + brand, brand, str(product_id), str(sku_id))

                sku_model_dir = sku_dir.joinpath("model")
                sku_model_dir.mkdir(parents=True, exist_ok=True)
                for index, url in enumerate(image_urls):
                    log.info(f"图片{url=}")
                    image_tasks.append(
                        fetch_images(
                            semaphore=semaphore,
                            url=url,
                            # headers=headers,
                            # cookies=cookies,
                            file_path=sku_model_dir.joinpath(f"model-{(index + 1):02d}-{url.split('/')[-1]}"),
                        )
                    )

                image_download_status = await asyncio.gather(*image_tasks)
                if all(image_download_status) and len(image_download_status) > 0:
                    r = redis.from_url(settings.redis_dsn, decode_responses=True, protocol=3)
                    async with r:
                        if task_type == "category":
                            await r.set(
                                f"image_download_status:{source}:{product_id}:{sku_id}",
                                "done",
                            )
                        elif task_type == "brand":
                            await r.set(
                                f"image_download_status_brand:{source}:{brand}:{product_id}:{sku_id}",
                                "done",
                            )
                        log.warning(f"商品图片: {product_id}, sku:{sku_id}, 图片下载完成, 标记状态为done")
                else:
                    log.warning(f"商品图片: {product_id}, sku:{sku_id}, 图片下载失败, 标记为failed")
                    r = redis.from_url(settings.redis_dsn, decode_responses=True, protocol=3)
                    async with r:
                        if task_type == "category":
                            await r.set(
                                f"image_download_status:{source}:{product_id}:{sku_id}",
                                "failed",
                            )
                        elif task_type == "brand":
                            await r.set(
                                f"image_download_status_brand:{source}:{brand}:{product_id}:{sku_id}",
                                "done",
                            )
                    log.warning("商品图片抓取失败")
    product_name = product.get("item").get("product_description").get("title")[:128] if product.get("item") else None
    raw_attributes = product.get("item").get("product_description").get("bullet_descriptions", [])
    try:
        attributes = {
            re.sub(r"\s+", "_", key.strip()).lower(): value.strip()
            for key, value in (
                re.sub(r"</?b>", "", field, flags=re.IGNORECASE).split(":", 1) for field in raw_attributes
            )
        }
    except Exception as exc:
        log.error(f"转换属性失败. 原字符串:{raw_attributes}, 异常提示: {exc}")
        attributes = None
    # TODO  对属性进行映射和序列化
    description = product.get("item", {}).get("product_description", {}).get("downstream_description", "")[:1024]
    price = product.get("price", {}).get("formatted_current_price")
    brand = product.get("item", {}).get("primary_brand", {}).get("name")
    product_obj = dict(
        product_id=product_id,  # 商品ID
        primary_sku_id=sku_id,  # sku_id
        product_name=product_name,  # 产品名称
        category=category,  # 类别
        parent_category=parent_category,  # 父级类别, 用于推断性别
        rating=rating,  # 评分
        rating_count=rating_count,  # 评分数
        brand=brand,  # 品牌
        product_url=product_url,  # 商品链接
        image_url=image_url,  # 商品图片
        outer_image_url=image_url,
        price=price,  # 价格
        size=size,
        color=color,
        source=source,  # 来源
        # model_image_url=alternate_image_urls[0] if len(alternate_image_urls) > 0 else None,
        # outer_model_image_url=alternate_image_urls[0] if len(alternate_image_urls) > 0 else None,
        # model_image_urls=image_urls,
        # outer_model_image_urls=image_urls,
        attributes=attributes,  # 商品属性
        description=description,  # 描述信息
        review_count=review_count,  # 评论数
        gender=primary_category,  # 大类别
        inner_category=sub_category,  # 内部类别
        sub_category=sub_category,  # 子类别
    )
    sku_obj = dict(
        product_id=product_id,  # 商品ID
        sku_id=sku_id,  # sku_id
        source=source,  # 来源
        product_url=product_url,  # sku链接
        # sku_name=color,  # sku名称
        color=color,  # 颜色
        size=size,  # 尺寸
        image_url=image_url,  # 商品图片
        outer_image_url=image_url,
        model_image_urls=image_urls,
        outer_model_image_urls=image_urls,

    )
    # 保存产品信息到数据库
    return product_obj, sku_obj


async def parse_plp_api_by_category(data: dict) -> tuple[dict, list]:
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


def parse_target_product_variation(data: dict) -> list[dict] | None:
    """
    解析target商品变体信息
    示例url
    https://redsky.target.com/redsky_aggregations/v1/web/pdp_variation_hierarchy_v1?key=9f36aeafbe60771e321a7cc95a78140772ab3e96&tcin=89766757&scheduled_delivery_store_id=1771&store_id=1771&latitude=41.9831&longitude=-91.6686&zip=52404&state=IA&visitor_id=018FBCFF654F0201A835C6E19137AC6F&channel=WEB&page=%2Fp%2FA-89766757
    """
    product: dict = data.get("data").get("product") if data.get("data") else None
    if not product:
        return None
    product_id = product.get("tcin") if product.get("tcin") else None
    size_layers: list = product.get("variation_hierarchy", [])
    skus = []
    for size_layer in size_layers:
        size = size_layer.get("value")
        color_layers: list = size_layer.get("variation_hierarchy", [])
        for color_layer in color_layers:
            color = color_layer.get("value")
            sku_id = color_layer.get("tcin")
            sku_url = color_layer.get("buy_url")
            image_url = color_layer.get("primary_image_url")
            sku = dict(
                product_id=product_id,  # 商品ID
                sku_id=sku_id,  # sku_id
                sku_url=sku_url,  # sku链接
                image_url=image_url,  # 图片链接
                sku_name=color,  # sku名称
                color=color,  # 颜色
                size=size,  # 尺寸
                source="target",  # 来源
            )
            skus.append(sku)
    # 将商品SKU保存到数据库
    # save_sku_data(skus)
    return skus

    pass


def map_attribute_field(input: dict) -> dict:
    """
    映射属性字段
    """
    # TODO 字段
    # input.get()

    return input

    pass


# async def scroll_page(page: Page, scroll_pause_time: int = 1000):
#     viewport_height = await page.evaluate("window.innerHeight")
#     i = 0
#     current_scroll_position = 0
#     while True:
#         # 滚动视口高度
#         i += 1
#         # log.info(f"第{i}次滚动, 滚动高度: {viewport_height}")
#         current_scroll_position += viewport_height
#         # log.info(f"当前滚动位置: {current_scroll_position}")
#         # 滚动到新的位置
#         await page.evaluate(f"window.scrollTo(0, {current_scroll_position})")
#         # 滚动到页面底部
#         # await page.evaluate(f"window.scrollTo(0, document.body.scrollHeight)")
#         await asyncio.sleep(scroll_pause_time / 1000)
#         # await page.wait_for_timeout(scroll_pause_time)
#         await page.wait_for_load_state("domcontentloaded")
#         # 重新获取页面高度
#         scroll_height = await page.evaluate("document.body.scrollHeight")
#         # 获取当前视口位置
#         current_viewport_position = await page.evaluate("window.scrollY + window.innerHeight")
#         # log.info(f"页面高度: {scroll_height}")
#         # log.info(f"当前视口位置: {current_viewport_position}")
#
#         if current_viewport_position >= scroll_height or current_scroll_position >= scroll_height:
#             # log.info("滚动到底部")
#             break
#         # previous_height = new_height


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
    urls = []

    default_urls = [

        ("furniture", "beds", "default", "default",
         "https://www.target.com/c/beds-bedroom-furniture/-/N-4ym22"),
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
        # ("women", "shorts", "black", "M",
        #  "https://www.target.com/c/shorts-women-s-clothing/-/N-5xtc5Zvef8aZ5y761?moveTo=product-list-grid"),  # 已完成
    ]
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

        # ("pets", "gifts-for-pets", "batch2", "unknown",
        #  "https://www.target.com/c/gifts-for-pets/-/N-55z1mZ5n5p5?moveTo=product-list-grid"
        #  ),
        ("pets", "gifts-for-pets", "batch3", "unknown",
         "https://www.target.com/c/gifts-for-pets/-/N-55z1mZzebtaZ4ycp2Z5n4heZ1pthuZ5n4hgZ55k79Z5n4hdZ9fm9hZsqpmwnp13q0Z5n5ofZ5n5k1Zsqpmwnqs6mxZ5n4o7?moveTo=product-list-grid"
         ),
    ]
    urls.extend(pet_urls)
    bed_urls = [
        ("furniture", "beds", "black", "default",
         "https://www.target.com/c/beds-bedroom-furniture/-/N-4ym22Z5y761?moveTo=product-list-grid"),
    ]
    # urls.extend(bed_urls)
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