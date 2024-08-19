__doc__ = """
# 按类别搜索
DOM
API示例:
https://search-api.jcpenney.com/v1/search-service/g/women/skirts?productGridView=medium&id=cat100250097&responseType=organic
首先, 获取类别信息, 然后逐一获取每个类别下面的商品信息

"""

import asyncio
import json
import os
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import httpx
import redis.asyncio as redis
from fake_useragent import UserAgent
from playwright.async_api import async_playwright, Route

from crawler.config import settings
from crawler.deps import get_logger
from crawler.store import save_product_data_async, save_product_detail_data_async, save_sku_data_async
from projects.jcpenney.common import cancel_requests

log = get_logger("jcpenney")
domain = "https://www.jcpenney.com"
image_base_url = "https://jcpenney.scene7.com/is/image/JCPenney"  # 图片基础地址, 用于拼接图片
image_max_params = "?hei=1500&wid=1500&resmode=sharp2&op_sharpen=1"  # 高清图片参数
source = "jcpenney"


def parse_category_from_api(data: dict) -> tuple[list[dict], list[str], dict]:
    """
    通过API解析类别数据
    """
    status_code = data.get("statusCode")
    if status_code != 200:
        log.error(f"请求失败: {data}")
        return [], [], {}
    parsed_products = []

    product_info = data.get("organicZoneInfo", {})
    total_count = product_info.get("totalNumRecs", 0)
    total_page = product_info.get("totalPages", 0)
    pagination = dict(
        total_count=total_count,
        total_page=total_page,
        current_page=product_info.get("currentPage", 0),
        page_size=48,
        offset=product_info.get("nextPageOffset", 0)
    )
    log.debug(f"解析到分页信息: {pagination=}")
    products: list[dict] = product_info.get("products", [])
    product_urls: list[str] = []
    for product in products:
        sku_id = product.get("skuId", None)
        product_url: str | None = product.get("pdpUrl", None)
        if product_url:
            product_url = domain + product_url.replace(domain, "")
            product_url = str(httpx.URL(product_url).copy_with(query=None).copy_add_param("selectedSKU",
                                                                                          sku_id).copy_add_param(
                "pTmplType", "regular"))
        released_at_str = product.get("firstActivationDate")
        # log.debug(f"{released_at_str=}")
        if released_at_str and released_at_str.startswith("20"):
            released_at = datetime.strptime(released_at_str, "%Y-%m-%dT%H:%M:%S")
        else:
            released_at = None
        sku_infos: list[dict] = product.get("skuSwatch", [])
        sku_data = dict(
            sku_id=sku_id,
        )
        for sku_info in sku_infos:
            if sku_info.get("skuId") == sku_id:
                image_url = image_base_url + "/" + sku_info.get("colorizedImageId") + image_max_params if sku_info.get(
                    "colorizedImageId") else None

                image_urls = [image_url] if image_url else []
                for image_data in sku_info.get("skuAltImages", []):
                    image_urls.append(image_base_url + "/" + image_data.get("imgId") + image_max_params)

                sku_data.update(color=sku_info.get("colorName"),
                                image_url=image_url,
                                model_image_urls=image_urls,
                                outer_image_url=image_url,
                                outer_model_image_urls=image_urls)

        parsed_product = dict(
            product_id=product.get("ppId", None),
            source="jcpenney",
            product_name=product.get("name")[:128] if product.get("name", None) else None,
            brand=product.get("brand", None),
            price=product.get("currentMin", None),
            rating=product.get("averageRating", None),
            review_count=product.get("reviewCount", None),
            sku_id=sku_id,
            primary_sku_id=sku_id,
            product_url=product_url,
            sku_url=product_url,
            color=sku_data.get("color", None),
            image_url=sku_data.get("image_url", None),
            model_image_urls=sku_data.get("model_image_urls", []),
            outer_image_url=sku_data.get("outer_image_url", None),
            outer_model_image_urls=sku_data.get("outer_model_image_urls", []),
            currency=product.get("currencyCode", None),
            released_at=released_at
        )
        parsed_products.append(parsed_product)
        if product_url:
            product_urls.append(product_url)
    log.debug(f"解析到商品数量: {len(parsed_products)}, {product_urls=}")

    return parsed_products, product_urls, pagination


async def run(main_category: str, sub_category: str, url: str):
    """
    获取类别数据
    """
    r = redis.from_url(settings.redis_dsn, decode_responses=True, protocol=3)
    async with r:
        category_key = f"category_task_status:{source}:{main_category}:{sub_category}:{url}"
        category_task_status = await r.get(category_key)
        if category_task_status == "done":
            log.info(f"已经抓取过: {main_category=}, {sub_category=}, {url=}")
            return
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=False)
        ua = UserAgent(browsers=["edge", "chrome", "safari"], platforms=["pc", "mobile"],
                       os=["windows", "macos", "android", "ios"])

        context = await browser.new_context(
            user_agent=ua.random,
        )
        # page = await browser.new_page()
        page = await context.new_page()
        async with page:
            await cancel_requests(page)
            log.info(f"开始任务: {main_category=}, {sub_category=}, 首页地址：{url}")
            products: list[dict] | None = []
            product_urls: list[str] | None = []
            route_event = asyncio.Event()

            async def handle_route(route: Route):
                url = route.request.url
                log.debug(f"当前url: {route.request.url}")
                request = route.request
                response = await route.fetch()
                data: dict = await response.json()
                nonlocal products
                nonlocal product_urls
                products, product_urls, pagination = parse_category_from_api(data=data)
                total_page = pagination.get("total_page", 0)

                if total_page > 1:
                    log.debug(f"总页数: {total_page}")
                    tasks = []
                    semaphore = asyncio.Semaphore(5)
                    for page in range(2, total_page + 1):
                        next_url = str(httpx.URL(url).copy_set_param("page", page))
                        log.debug(f"跳转到下一页: {next_url}")
                        tasks.append(fetch_product_urls(next_url, semaphore, request.headers))
                    extra_products = await asyncio.gather(*tasks)

                    # 将每个分页获取到商品信息和url 合并到一起
                    for sub_products, sub_product_urls in extra_products:
                        products.extend(sub_products)
                        product_urls.extend(sub_product_urls)
                else:
                    log.debug(f"只有一页: {total_page}")
                log.debug(f"获取到商品数量: {len(products)}")
                log.debug(f"路由事件执行完毕, url={url}")
                route_event.set()

                pass

            await page.route("**/search-api.jcpenney.com/v1/search-service/**", handle_route)

            await page.goto(url)

            await page.wait_for_load_state("domcontentloaded")

            await page.wait_for_timeout(10000)

            # elements = await page.query_selector_all(
            #     'div[data-automation-id="zone-Navigation"] li > a'
            # )
            # 
            # urls = []
            # for element in elements:
            #     url = await element.get_attribute("href")
            #     urls.append("https://www.jcpenney.com" + url)
            try:
                await asyncio.wait_for(route_event.wait(), timeout=60 * 2)
                # 将商品url 保存到redis
                log.debug(f"获取到商品数量: {len(product_urls)}")
                async with r:
                    if product_urls:

                        inserted_count = await r.sadd(f"{source}:{main_category}:{sub_category}", *product_urls)
                        log.info(f"保存商品url到redis: {inserted_count=}")
                        # category_key = f"category_task_status:{source}:{main_category}:{sub_category}:{url}"
                        await r.set(category_key, "done")
                        log.info(f"设置任务状态: {category_key=} 商品索引建立完成")

                    else:
                        log.warning(f"没有获取到商品url: {main_category=}, {sub_category=}")

                # await page.pause()
                await save_product_data_async(products)
                await save_product_detail_data_async(products)
                await save_sku_data_async(products)

            except TimeoutError:
                log.warning("获取商品信息超时")
            except Exception as e:
                log.error(f"Error: {e}")
        await browser.close()


"""
第二步
获取商品列表信息
"""


# CACHE_PATH = "projects/jcpenney/cache.json"


async def fetch_product_urls(url: str, semaphore: asyncio.Semaphore, headers: dict) -> tuple[
    list[dict], list[str]]:
    async with semaphore:
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.get(url, headers=headers)
                data = response.json()
                products, product_urls, _ = parse_category_from_api(data)
                return products, product_urls
        except Exception as e:
            log.error(f"Error: {e}")
            return [], []


def update_url_page(url: str, next_page_num: int) -> str:
    """替换翻页的 url"""
    parsed_url = urlparse(url)
    query = parse_qs(parsed_url.query)

    query["page"] = [next_page_num]  # 参数值应为列表形式以适应 urlencode 方法
    new_query_string = urlencode(query, doseq=True)
    new_url = parsed_url._replace(query=new_query_string)
    updated_url = urlunparse(new_url)

    return updated_url


async def handle_items_url(page, json_file_path: str):
    """获取并去重商品列表的 url"""

    # TODO 获取urls
    elements = await page.query_selector_all(
        "div#gallery-product-list div.list-body li div.gallery + a"
    )
    urls = [
        "https://www.jcpenney.com" + await element.get_attribute("href")
        for element in elements
    ]
    urls = list(set(urls))
    with open(json_file_path, "w") as f:
        json.dump(urls, f, indent=4)


async def fetch_page(page, filename: str, page_num: int, last_page_num: str):
    """
    保存item数据到json
    """

    folder = f"projects/jcpenney/data/{filename}"
    json_filename = f"{filename}_{page_num}.json"
    os.makedirs(folder, exist_ok=True)

    # 处理已经抓取过的内容
    if os.path.exists(f"{folder}/{json_filename}"):
        log.debug(f"已经抓取过: {folder}/{json_filename}")
        # 查看下一个未抓取的内容
        next_json_filename: str = f"{filename}_{page_num + 1}.json"
        next_json_path: str = os.path.join(folder, next_json_filename)

        while os.path.exists(next_json_path) and page_num < int(last_page_num):
            page_num += 1
            log.debug(
                f"已经抓取过:  {folder}/{json_filename}, 查看下一个未抓取的内容: {next_json_path}"
            )
            next_json_filename = f"{filename}_{page_num + 1}.json"
            next_json_path = os.path.join(folder, next_json_filename)

        if page_num > int(last_page_num) and os.path.exists(next_json_path):
            log.debug(f"已达到最大页数: {page_num}")
            return last_page_num + 1

        await page.wait_for_timeout(10000)
        return page_num

    if page_num > 1:
        await page.wait_for_timeout(10000)

    log.info(f"fetching page {page_num}")

    json_file_path: str = f"{folder}/{json_filename}"
    await handle_items_url(page, json_file_path)

    await page.wait_for_timeout(3000)
    return page_num


async def fetch_item_list(url: str):
    log.info("=" * 50)
    log.info(f"开始任务 - 首页地址：{url}")
    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(headless=False, timeout=60000)
            context = await browser.new_context(storage_state=settings.user_data_dir.joinpath("state.json"))
            page = await context.new_page()
            await cancel_requests(page)

            # 想拿到 women_tops 的string
            file_url = url.replace("https://www.jcpenney.com/g/", "").split("?")[0]
            filename = file_url.replace("/", "_")
            await page.goto(url)
            await page.wait_for_timeout(10000)

            # 获取总页数
            last_page = page.locator(
                "div.pagination-container > div >div:last-of-type"
            )
            last_page_num = await last_page.inner_text()
            log.info(f"一共: {last_page_num} 页内容")

            # TODO 优化翻页逻辑
            page_num = 1
            next_page_num = await fetch_page(page, filename, page_num, last_page_num)
            if next_page_num > int(last_page_num):
                await browser.close()
                return

            next_button = await page.query_selector("//button[contains(., 'Next')]")
            while next_button:
                try:
                    next_page_num += 1
                    if next_page_num > int(last_page_num):
                        await browser.close()
                        log.info("抓取完毕")
                        return

                    await next_button.scroll_into_view_if_needed()

                    next_url = update_url_page(url, next_page_num)
                    log.info(f"跳转到 {next_url}")
                    await page.goto(next_url, timeout=60000)
                    # await next_button.click(timeout=60000)
                    next_page_num = await fetch_page(
                        page, filename, next_page_num, last_page_num
                    )
                except:
                    await page.reload()
                    await page.wait_for_timeout(10000)
                    pass
                next_button = await page.query_selector("//button[contains(., 'Next')]")
        except Exception as e:
            log.error(f"Error: {e}")
        finally:
            await browser.close()


def clean():
    """
    清洗数据中的重复内容
    """
    for folder in Path("projects/jcpenney/data").glob("*"):
        print(folder)
        data = []
        for f in folder.glob("*.json"):
            print(f)
            with open(f, "r", encoding="utf-8") as file:
                data.extend(json.load(file))

        Path("projects/jcpenney/clean_data").mkdir(exist_ok=True, parents=True)
        with open(
                f"projects/jcpenney/clean_data/{folder.stem}.json", "w", encoding="utf-8"
        ) as file:
            data = list(set(data))
            json.dump(data, file, indent=4)


async def main():
    loop = asyncio.get_running_loop()
    num_processes = os.cpu_count() // 2
    num_processes = 4
    log.info(f"CPU核心数: {os.cpu_count()}, 进程数: {num_processes}")
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
    # categories = [
    # 
    #     ("men", "shirts",
    #      "https://www.jcpenney.com/g/men/mens-shirts?id=cat100240025&cm_re=ZJ-_-DEPARTMENT-MEN-_-VN-_-CATEGORIES-_-SHIRTS_1"),
    # ]
    categories = [('jewelry-and-watches', 'jewelry-and-watches',
                   'https://www.jcpenney.com/g/jewelry-and-watches?new_arrivals=view+all+new&id=dept20000020&cm_re=ZC-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-BLK-FRI-22-_-SHOP-ALL-JEWELRY-NEW-ARRIVALS_1'),
                  ('jewelry-and-watches', 'engagement-rings',
                   'https://www.jcpenney.com/g/jewelry-and-watches/engagement-rings?id=cat1009920002&cm_re=ZD-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_FineJewelry_EngagementRings_1'),
                  ('jewelry-and-watches', 'view-all-modern-bride',
                   'https://www.jcpenney.com/g/jewelry-and-watches/view-all-modern-bride?ring_style=wedding+bands&id=cat1004860021&cm_re=ZD-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_FineJewelry_WeddingBands_2'),
                  ('jewelry-and-watches', 'rings',
                   'https://www.jcpenney.com/g/jewelry-and-watches/rings?mktTiles=0&id=cat100240086&cm_re=ZD-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_FineJewelry_FineRings_3'),
                  ('jewelry-and-watches', 'earrings',
                   'https://www.jcpenney.com/g/jewelry-and-watches/earrings?mktTiles=0&id=cat100240094&cm_re=ZD-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_FineJewelry_FineEarrings_4'),
                  ('jewelry-and-watches', 'necklaces-pendants',
                   'https://www.jcpenney.com/g/jewelry-and-watches/necklaces-pendants?mktTiles=0&id=cat100240093&cm_re=ZD-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_FineJewelry_FineNecklaces_5'),
                  ('jewelry-and-watches', 'bracelets',
                   'https://www.jcpenney.com/g/jewelry-and-watches/bracelets?mktTiles=0&id=cat100240096&cm_re=ZD-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_FineJewelry_FineBracelets_6'),
                  ('jewelry-and-watches', 'fine-jewelry-sets',
                   'https://www.jcpenney.com/g/jewelry-and-watches/fine-jewelry-sets?mktTiles=0&id=cat100260194&cm_re=ZD-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_FineJewelry_FineJewelrySets_7'),
                  ('jewelry-and-watches', 'fine-jewelry',
                   'https://www.jcpenney.com/g/jewelry-and-watches/fine-jewelry?features=in+a+gift+box&mktTiles=0&id=cat100260192&cm_re=ZD-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_FineJewelry_RedBowDeals_8'),
                  ('jewelry-and-watches', 'fine-jewelry',
                   'https://www.jcpenney.com/g/jewelry-and-watches/fine-jewelry?mktTiles=0&id=cat100260192&cm_re=ZD-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_FineJewelry_AllFineJewelry_9'),
                  ('jewelry-and-watches', 'view-all-modern-bride',
                   'https://www.jcpenney.com/g/jewelry-and-watches/view-all-modern-bride?mktTiles=0&id=cat1004860021&cm_re=ZE-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_FeaturedCategories_WeddingJewelry_1'),
                  ('jewelry-and-watches', 'diamond-jewelry',
                   'https://www.jcpenney.com/g/jewelry-and-watches/diamond-jewelry?mktTiles=0&id=cat100260184&cm_re=ZE-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_FeaturedCategories_DiamondJewelry_2'),
                  ('jewelry-and-watches', 'birthstone-jewelry',
                   'https://www.jcpenney.com/g/jewelry-and-watches/birthstone-jewelry?id=cat10010020003&cm_re=ZE-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_FeaturedCategories_BirthstoneJewelry_3'),
                  ('jewelry-and-watches', 'gemstone-jewelry',
                   'https://www.jcpenney.com/g/jewelry-and-watches/gemstone-jewelry?id=cat1003050007&cm_re=ZE-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_FeaturedCategories_GemstoneJewelry_4'),
                  ('jewelry-and-watches', 'mens-jewelry',
                   'https://www.jcpenney.com/g/jewelry-and-watches/mens-jewelry?mktTiles=0&id=cat100260183&cm_re=ZE-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_FeaturedCategories_MensJewelry_5'),
                  ('jewelry-and-watches', 'fine-jewelry',
                   'https://www.jcpenney.com/g/jewelry-and-watches/fine-jewelry?age_group=kids&id=cat100260192&cm_re=ZE-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_FeaturedCategories_KidsJewelry_6'),
                  ('jewelry-and-watches', 'pearl-earrings-necklaces',
                   'https://www.jcpenney.com/g/jewelry-and-watches/pearl-earrings-necklaces?mktTiles=0&id=cat1003050008&cm_re=ZE-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_FeaturedCategories_PearlJewelry_7'),
                  ('jewelry-and-watches', 'gold-jewelry',
                   'https://www.jcpenney.com/g/jewelry-and-watches/gold-jewelry?id=cat100260186&cm_re=ZE-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_FeaturedCategories_GoldJewelry_8'),
                  ('jewelry-and-watches', 'silver-jewelry',
                   'https://www.jcpenney.com/g/jewelry-and-watches/silver-jewelry?id=cat100260187&cm_re=ZE-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_FeaturedCategories_SilverJewelry_9'),
                  ('jewelry-and-watches', 'fine-jewelry',
                   'https://www.jcpenney.com/g/jewelry-and-watches/fine-jewelry?mktTiles=0&id=cat100260192&stone=cubic+zirconia%7Cmoissanite&cm_re=ZE-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_FeaturedCategories_AlternativeDiamondJewelry_10'),
                  ('jewelry-and-watches', 'jewelry-and-watches',
                   'https://www.jcpenney.com/g/jewelry-and-watches?division=005&features=in+a+gift+box&id=dept20000020&cm_re=ZE-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_FeaturedCategories_BoxedJewelry_11'),
                  ('jewelry-and-watches', 'personalized-jewelry',
                   'https://www.jcpenney.com/d/jewelry-watches/personalized-jewelry?cm_re=ZE-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_FeaturedCategories_PersonalizedJewelry_12'),
                  ('jewelry-and-watches', 'jewelry-and-watches',
                   'https://www.jcpenney.com/g/jewelry-and-watches?features=religious+jewelry&id=dept20000020&cm_re=ZE-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_FeaturedCategories_ReligiousJewelry_13'),
                  ('jewelry-and-watches', 'charms-charm-bracelets',
                   'https://www.jcpenney.com/g/jewelry-and-watches/charms-charm-bracelets?id=cat10010990003&cm_re=ZE-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_FeaturedCategories_CharmsCharmBracelets_14'),
                  ('jewelry-and-watches', 'jewelry-armoires-boxes',
                   'https://www.jcpenney.com/g/jewelry-and-watches/jewelry-armoires-boxes?id=cat100250007&cm_re=ZE-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_FeaturedCategories_JewelryBoxesArmoires_15'),
                  ('jewelry-and-watches', 'fashion-necklaces-pendants',
                   'https://www.jcpenney.com/g/jewelry-and-watches/fashion-necklaces-pendants?mktTiles=0&id=cat100260188&cm_re=ZF-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_FashionJewelry_FashionNecklaces_1'),
                  ('jewelry-and-watches', 'fashion-earrings',
                   'https://www.jcpenney.com/g/jewelry-and-watches/fashion-earrings?mktTiles=0&id=cat100260190&cm_re=ZF-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_FashionJewelry_FashionEarrings_2'),
                  ('jewelry-and-watches', 'fashion-bracelets',
                   'https://www.jcpenney.com/g/jewelry-and-watches/fashion-bracelets?mktTiles=0&id=cat100260189&cm_re=ZF-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_FashionJewelry_FashionBracelets_3'),
                  ('jewelry-and-watches', 'fashion-rings',
                   'https://www.jcpenney.com/g/jewelry-and-watches/fashion-rings?mktTiles=0&id=cat100260191&cm_re=ZF-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_FashionJewelry_FashionRings_4'),
                  ('jewelry-and-watches', 'fashion-jewelry-sets',
                   'https://www.jcpenney.com/g/jewelry-and-watches/fashion-jewelry-sets?mktTiles=0&id=cat1002700041&cm_re=ZF-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_FashionJewelry_FashionJewelrySets_5'),
                  ('jewelry-and-watches', 'fashion-jewelry',
                   'https://www.jcpenney.com/g/jewelry-and-watches/fashion-jewelry?subdivision=058&mktTiles=0&id=cat100240091&cm_re=ZF-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_FashionJewelry_FashionSilver_6'),
                  ('jewelry-and-watches', 'fashion-jewelry',
                   'https://www.jcpenney.comhttps://www.jcpenney.com/g/jewelry-and-watches/fashion-jewelry?id=cat100240091&Nf=PR+1+10&cm_re=ZF-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_FashionJewelry_10AndUnder_7'),
                  ('jewelry-and-watches', 'fashion-jewelry',
                   'https://www.jcpenney.com/g/jewelry-and-watches/fashion-jewelry?id=cat100240091&cm_re=ZF-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_FashionJewelry_ViewAllFashionJewelry_8'),
                  ('jewelry-and-watches', 'mens-watches',
                   'https://www.jcpenney.com/g/jewelry-and-watches/mens-watches?mktTiles=0&id=cat1002300029&cm_re=ZG-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_Watches_MensWatches_1'),
                  ('jewelry-and-watches', 'womens-watches',
                   'https://www.jcpenney.com/g/jewelry-and-watches/womens-watches?mktTiles=0&id=cat1002300028&cm_re=ZG-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_Watches_WomensWatches_2'),
                  ('jewelry-and-watches', 'kids-watches',
                   'https://www.jcpenney.com/g/jewelry-and-watches/kids-watches?mktTiles=0&id=cat1002300030&cm_re=ZG-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_Watches_KidsWatches_3'),
                  ('jewelry-and-watches', 'jewelry-and-watches',
                   'https://www.jcpenney.com/g/jewelry-and-watches?item_type=fitness+trackers%7Csmart+watches&id=dept20000020&cm_re=ZG-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_Watches_ActiveSmartWatches_4'),
                  ('jewelry-and-watches', 'jewelry-and-watches',
                   'https://www.jcpenney.com/g/jewelry-and-watches?subdivision=051%7C060&mktTiles=0&id=dept20000020&cm_re=ZG-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_Watches_FineWatches_5'),
                  ('jewelry-and-watches', 'fashion-watches',
                   'https://www.jcpenney.com/g/jewelry-and-watches/fashion-watches?mktTiles=0&id=cat1003480102&cm_re=ZG-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_Watches_FashionWatches_6'),
                  ('jewelry-and-watches', 'all-watches',
                   'https://www.jcpenney.com/g/jewelry-and-watches/all-watches?id=cat100240089&Nf=PR+0.00+50.00&cm_re=ZG-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_Watches_50AndUnderWatches_7'),
                  ('jewelry-and-watches', 'all-watches',
                   'https://www.jcpenney.com/g/jewelry-and-watches/all-watches?mktTiles=0&id=cat100240089&cm_re=ZG-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_Watches_ViewAllWatches_8'),
                  ('jewelry-and-watches', 'name-initial-monogram',
                   'https://www.jcpenney.com/g/jewelry-and-watches/personalized-jewelry/name-initial-monogram?mktTiles=0&id=cat1005850002&cm_re=ZH-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_PersonalizedJewelry_NameInitialMonogram_1'),
                  ('jewelry-and-watches', 'artcarved-moms-jewelery',
                   'https://www.jcpenney.comhttps://personalizedjewelry.jcpenney.com/shop/category/artcarved-moms-jewelery?cm_re=ZH-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_PersonalizedJewelry_ArtcarvedMomJewelry_2'),
                  ('jewelry-and-watches', 'college-class-rings',
                   'https://www.jcpenney.comhttps://personalizedjewelry.jcpenney.com/shop/category/college-class-rings?cm_re=ZH-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_PersonalizedJewelry_ArtcarvedClassRings_3'),
                  ('jewelry-and-watches', 'couples-and-commitment',
                   'https://www.jcpenney.comhttps://personalizedjewelry.jcpenney.com/shop/category/couples-and-commitment?cm_re=ZH-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_PersonalizedJewelry_CouplesCommitmentRings_4'),
                  ('jewelry-and-watches', 'family-jewelry',
                   'https://www.jcpenney.com/g/jewelry-and-watches/personalized-jewelry/family-jewelry?mktTiles=0&id=cat1005820003&cm_re=ZH-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_PersonalizedJewelry_Family_5'),
                  ('jewelry-and-watches', 'military-and-service',
                   'https://www.jcpenney.comhttps://personalizedjewelry.jcpenney.com/shop/theme/military-and-service?cm_re=ZH-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_PersonalizedJewelry_ArtcarvedMilitaryService_6'),
                  ('jewelry-and-watches', 'gemstone-jewelry',
                   'https://www.jcpenney.com/g/jewelry-and-watches/gemstone-jewelry?mktTiles=0&id=cat1003050007&cm_re=ZH-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_PersonalizedJewelry_Gemstone_7'),
                  ('jewelry-and-watches', 'children-baby-jewelry',
                   'https://www.jcpenney.com/g/jewelry-and-watches/personalized-jewelry/children-baby-jewelry?mktTiles=0&id=cat1005820004&cm_re=ZH-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_PersonalizedJewelry_ChildrenBaby_8'),
                  ('jewelry-and-watches', 'quinceanera-sweet-16-and-teen-jewelry',
                   'https://www.jcpenney.comhttps://personalizedjewelry.jcpenney.com/shop/category/quinceanera-sweet-16-and-teen-jewelry?cm_re=ZH-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_PersonalizedJewelry_QuinceaneraSweet16Teen_9'),
                  ('jewelry-and-watches', 'personalized-watches',
                   'https://www.jcpenney.com/g/jewelry-and-watches/personalized-jewelry/personalized-watches?mktTiles=0&id=cat1005800005&cm_re=ZH-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_PersonalizedJewelry_PersonalizedWatches_10'),
                  ('jewelry-and-watches', 'fashion-jewelry',
                   'https://www.jcpenney.com/g/jewelry-and-watches/fashion-jewelry?mktTiles=0&id=cat100240091&brand=bijoux+bar&cm_re=ZI-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_Brands_BijouxBar_1'),
                  ('jewelry-and-watches', 'all-watches',
                   'https://www.jcpenney.com/g/jewelry-and-watches/all-watches?mktTiles=0&id=cat100240089&brand=bulova&cm_re=ZI-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_Brands_Bulova_2'),
                  ('jewelry-and-watches', 'all-watches',
                   'https://www.jcpenney.com/g/jewelry-and-watches/all-watches?mktTiles=0&id=cat100240089&brand=citizen%7Ccitizen+quartz%7Cdrive+from+citizen+eco-drive&cm_re=ZI-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_Brands_Citizen_3'),
                  ('jewelry-and-watches', 'jewelry-and-watches',
                   'https://www.jcpenney.com/g/jewelry-and-watches?mktTiles=0&id=dept20000020&jewelry_brand=diamonart&cm_re=ZI-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_Brands_Diamonart_4'),
                  ('jewelry-and-watches', 'effy',
                   'https://www.jcpenney.com/g/jewelry-and-watches/all-fine-jewelry/effy?id=cat11100003643&cm_re=ZI-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-EFFY_5'),
                  ('jewelry-and-watches', 'enchanted-disney-fine-jewelry',
                   'https://www.jcpenney.com/g/jewelry-and-watches/enchanted-disney-fine-jewelry?id=cat1009750001&cm_re=ZI-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_Brands_Disney_6'),
                  ('jewelry-and-watches', 'le-vian-fine-jewelry',
                   'https://www.jcpenney.com/g/jewelry-and-watches/le-vian-fine-jewelry?id=cat11100008053&cm_re=ZI-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_Brands_Levian_7'),
                  ('jewelry-and-watches', 'fashion-jewelry',
                   'https://www.jcpenney.com/g/jewelry-and-watches/fashion-jewelry?brand=liz+claiborne&id=cat100240091&cm_re=ZI-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_Brands_LizClaiborne_8'),
                  ('jewelry-and-watches', 'view-all-modern-bride',
                   'https://www.jcpenney.com/g/jewelry-and-watches/view-all-modern-bride?jewelry_brand=signature+by+modern+bride&id=cat1004860021&cm_re=ZI-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-SIGNATURE-BY-MODERN-BRIDE_9'),
                  ('jewelry-and-watches', 'fashion-jewelry',
                   'https://www.jcpenney.com/g/jewelry-and-watches/fashion-jewelry?mktTiles=0&id=cat100240091&brand=monet+jewelry&cm_re=ZI-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_Brands_Monet_10'),
                  ('jewelry-and-watches', 'all-watches',
                   'https://www.jcpenney.com/g/jewelry-and-watches/all-watches?mktTiles=0&id=cat100240089&brand=samsung&cm_re=ZI-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_Brands_Samsung_11'),
                  ('jewelry-and-watches', 'all-watches',
                   'https://www.jcpenney.com/g/jewelry-and-watches/all-watches?mktTiles=0&id=cat100240089&brand=timex&cm_re=ZI-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_Brands_Timex_12'),
                  ('jewelry-and-watches', 'jewelry-and-watches',
                   'https://www.jcpenney.com/g/jewelry-and-watches?division=005&mktTiles=0&view_all=view+all+brands&id=dept20000020&cm_re=ZI-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_Brands_ViewAllBrands_13'),
                  ('jewelry-and-watches', 'jewelry-education',
                   'https://www.jcpenney.com/m/jewelry-education?cm_re=ZJ-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_HelpfulInformation-1_JewelryEducation_1'),
                  ('jewelry-and-watches', 'jewelry-buying-guides',
                   'https://www.jcpenney.com/m/jewelry-buying-guides?cm_re=ZJ-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_HelpfulInformation-2_JewelryBuyingGuides_2'),
                  ('jewelry-and-watches', 'jewelry-and-watches',
                   'https://www.jcpenney.com/g/jewelry-and-watches?mktTiles=0&s1_deals_and_promotions=SALE&id=dept20000020&cm_re=ZK-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_SaleClearance_Sale_1'),
                  ('jewelry-and-watches', 'jewelry-and-watches',
                   'https://www.jcpenney.com/g/jewelry-and-watches?mktTiles=0&s1_deals_and_promotions=CLEARANCE&id=dept20000020&cm_re=ZK-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_SaleClearance_Clearance_2'),
                  ('jewelry-and-watches', 'jewelry-and-watches',
                   'https://www.jcpenney.com/g/jewelry-and-watches?division=005&subdivision=237%7C247%7C437%7C447&mktTiles=0&id=dept20000020&cm_re=ZK-_-DEPARTMENT-JEWELRY-AND-WATCHES-_-LF-_-Jewelry_SaleClearance_LimitedQuantities_3')]

    with ProcessPoolExecutor(max_workers=num_processes) as executor:
        tasks = [loop.run_in_executor(executor, async_runner, main_category, sub_category, url) for
                 main_category, sub_category, url in categories]
        task_results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in task_results:
            if isinstance(result, Exception):
                log.error(f"{result}")


def async_runner(main_category: str, sub_category: str, url: str):
    asyncio.run(run(main_category, sub_category, url))


if __name__ == "__main__":
    asyncio.run(main())
