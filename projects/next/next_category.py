import asyncio
import random

import redis.asyncio as redis
from playwright.async_api import Playwright, async_playwright

from crawler.config import settings
from crawler.deps import get_logger
from crawler.utils import scroll_page

log = get_logger("next")
log.info(f"日志配置成功, 日志器: {log.name}")

# log.debug(f"{PLAYWRIGHT_TIMEOUT=}")
settings.save_login_state = False
settings.playwright.headless = False


async def run(playwright: Playwright) -> None:
    # 从playwright对象中获取chromium浏览器
    chromium = playwright.chromium
    # 指定代理
    # proxy = {"server": "http://127.0.0.1:7890"}
    # 启动chromium浏览器，开启开发者工具，非无头模式
    # browser = await chromium.launch(headless=False, devtools=True)
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
            # headless=True,
            proxy=proxy,
            headless=settings.playwright.headless,
            # slow_mo=50,  # 每个操作的延迟时间（毫秒），便于调试
            args=["--start-maximized"],  # 启动时最大化窗口
            # ignore_https_errors=True,  # 忽略HTTPS错误
            # devtools=True,  # 打开开发者工具
        )
    else:
        browser = await chromium.launch(
            headless=settings.playwright.headless,
            # devtools=True, 
            proxy=proxy)
        context = await browser.new_context()

    # 设置全局超时
    context.set_default_timeout(settings.playwright.timeout)
    # context.set_default_timeout(60000)
    # 创建一个新的浏览器上下文，设置视口大小
    # context = await browser.new_context(viewport={"width": 1920, "height": 1080})
    # 在浏览器上下文中打开一个新页面

    # 打开新的页面
    # for base_url in urls:

    # 获取所有类别
    categories = [
        # ("dresses", "14340"),
        # ("tshirts", "4256"),
        # ("blouses", "4132"),
        # ("trousers", "3531"),
        # ("jackets", "2729"),
        # ("jumpers", "2310"),
        # ("skirts", "2131"),  # TODO160 之后没拿对, 原722条
        # ("shirts", "2081"),
        # ("jeans", "1901"),
        # ("shorts", "1841"),
        # ("bikinis", "1763"),
        # ("vests", "1380"),
        # ("jumpsuit", "1226"),
        # ("cardigans", "1041"),
        # ("coats", "971"),
        # ("leggings", "954"),
        # ("sweattops", "934"),
        # ("hoodies", "786"),
        # ("tunics", "660"),
        # ("joggers", "651"),
        # ("socks", "611"),
        # ("coverups", "600"),
        # ("tanktops", "471"),
        # ("camisoles", "408"),
        # ("fleeces", "320"),
        # ("waistcoats", "307"),
        # ("gilets", "249"),
        # ("bodies", "246"),
        # ("playsuits", "244"),
        # ("suitjackets", "185"),
        # ("poloshirts", "178"),
        # ("suittrousers", "156"),
        # ("tights", "154"),
        # ("croptops", "122"),
        # ("tankinis", "118"),
        # ("ponchos", "52"),
        # ("dungarees", "44"),
        # ("boobtube", "43"),
        # ("tracksuits", "32"),
        # ("rashvests", "27"),
        # ("bodysuits", "22"),
        # ("allinone", "13"),
        ("loungewearsets", "12"),
        ("topshortsets", "12"),
        ("blazers", "9"),
        ("topleggingset", "5"),
        ("suitskirts", "3"),
        ("rompersuits", "2"),
        ("snowsuits", "2"),
        ("dungareeset", "1"),
    ]
    # boys
    categories = [
        ("tshirts", "2339"),
        ("shorts", "1079"),
        ("shirts", "700"),
        ("hoodies", "629"),
        ("poloshirts", "556"),
        ("jackets", "535"),
        ("pyjamas", "515"),
        ("socks", "496"),
        ("trousers", "487"),
        ("joggers", "459"),
        ("swimshorts", "339"),
        ("jeans", "256"),
        ("sleepsuits", "219"),
        ("rompersuits", "207"),
        ("topshortsets", "189"),
        ("bodysuits", "187"),
        ("tracksuits", "137"),
        ("jumpers", "126"),
        ("rashvests", "109"),
        ("coats", "108"),
        ("dungarees", "105"),
        ("sweattops", "104"),
        ("trunks", "95"),
        ("sweattopjoggersets", "86"),
        ("footballshirts", "85"),
        ("boxers", "82"),
        ("cardigans", "75"),
        ("dungareeset", "63"),
        ("robes", "63"),
        ("sweattopshortset", "62"),
        ("allinone", "59"),
        ("leggings", "55"),
        ("gilets", "55"),
        ("swimsuits", "52"),
        ("fleeces", "50"),
        ("suittrousers", "48"),
        ("briefs", "47"),
        ("sunsafesuits", "46"),
        ("suitjackets", "42"),
        ("vests", "41"),
        ("topleggingset", "36"),
        ("puddlesuits", "35"),
        ("coverups", "31"),
        ("sleepsuitset", "29"),
        ("wetsuits", "28"),
        ("baselayers", "27"),
        ("waistcoats", "27"),
        ("shirttrouserset", "23"),
        ("hoodiejoggerset", "21"),
        ("pramsuits", "20"),
    ]
    # girls
    categories = [
        ("dresses", "2350"),
        ("tshirts", "1347"),
        ("shorts", "585"),
        ("leggings", "492"),
        ("pyjamas", "473"),
        ("sleepsuits", "439"),
        ("jackets", "433"),
        ("socks", "361"),
        ("hoodies", "349"),
        ("topshortsets", "347"),
        ("skirts", "303"),
        ("jeans", "280"),
        ("cardigans", "279"),
        ("sweattops", "275"),
        ("trousers", "266"),
        ("swimsuits", "262"),
        ("rompersuits", "240"),
        ("joggers", "206"),
        ("bodysuits", "202"),
        ("blouses", "175"),
        ("playsuits", "157"),
        ("topleggingset", "150"),
        ("vests", "141"),
        ("tights", "139"),
        ("briefs", "129"),
        ("coats", "120"),
        ("jumpsuit", "118"),
        ("jumpers", "99"),
        ("sunsafesuits", "91"),
        ("dungarees", "87"),
        ("rashvests", "68"),
        ("shirts", "67"),
        ("allinone", "64"),
        ("bras", "57"),
        ("nighties", "45"),
        ("sweattopleggingset", "44"),
        ("topskirtset", "44"),
        ("sweattopjoggersets", "41"),
        ("slippers", "39"),
        ("dressset", "38"),
        ("ponchos", "37"),
        ("puddlesuits", "37"),
        ("sweattopshortset", "37"),
        ("coverups", "36"),
        ("robes", "36"),
        ("fleeces", "33"),
        ("poloshirts", "32"),
        ("tracksuits", "29"),
        ("pramsuits", "28"),
        ("sleepsuitset", "28"),
    ]

    # men
    categories = [
        # ("tshirts", "3658"),
        # ("shirts", "2579"),
        # ("shorts", "1888"),
        # ("jackets", "1604"),
        # ("poloshirts", "1603"),
        # ("trousers", "1117"),
        # ("hoodies", "1070"),
        # ("sweattops", "654"),
        # ("socks", "652"),
        # ("joggers", "605"),
        # ("jeans", "576"),
        # ("jumpers", "512"),
        # ("footballshirts", "463"),
        # ("swimshorts", "421"),
        # ("suittrousers", "392"),
        # ("suitjackets", "386"),
        # ("fleeces", "248"),
        # ("waistcoats", "238"),
        # ("coats", "205"),
        # ("gilets", "181"),
        # ("vests", "142"),
        # ("tracksuits", "67"),
        # ("cardigans", "39"),
        # ("rashvests", "32"),
        # ("topshortsets", "23"),
        # ("rugbyshirts", "20"),
        # ("leggings", "14"),
        # ("ponchos", "6"),
        ("allinone", "4"),
        ("loungewearsets", "3"),
        ("sweattopjoggersets", "3"),
        ("tights", "3"),
        ("tanktops", "2"),
        # ("jumpsuit", "1"),
        # ("suits", "1"),
    ]
    # categories = [("bedding", 143)]
    categories = [('pets', 677)]

    # 床上用品
    # categories = [('bedsets', '1263'), ('throws', '577'), ('bedsheets', '435'), ('pillowcases', '399'),
    #               ('duvets', '238'), ('pillows', '161'), ('duvetcover', '100'), ('protectors', '66'), ('toppers', '39'),
    #               ('blankets', '10'), ('valances', '7')]
    categories = dict(
        baby=[
            ('dresses', '1095'),
            ('tshirts', '1056'), ('sleepsuits', '472'), ('jackets', '433'),
            ('shorts', '405'), ('socks', '328'), ('trousers', '300'), ('topshortsets', '278'), ('shirts', '252'),
            ('bodysuits', '210'), ('cardigans', '205'), ('leggings', '199'), ('hoodies', '187'),
            ('joggers', '179'), ('rompersuits', '173'), ('sweattops', '160'), ('coats', '157'),
            ('poloshirts', '150'), ('tights', '141'), ('topleggingset', '137'), ('dungarees', '121'),
            ('sweattopjoggersets', '115'), ('jumpers', '113'), ('jeans', '111'), ('skirts', '92'),
            ('rashvests', '77'), ('tracksuits', '77'), ('blouses', '69'), ('dungareeset', '58'),
            ('puddlesuits', '54'), ('allinone', '50'), ('vests', '48'), ('playsuits', '45'),
            ('sweattopleggingset', '40'), ('pramsuits', '34'), ('sweattopshortset', '34'), ('sleepsuitset', '33'),
            ('jumpsuit', '32'), ('fleeces', '31'), ('bikinis', '29'), ('coverups', '26'), ('gilets', '25'),
            ('ponchos', '25'), ('snowsuits', '22'), ('dressset', '19'), ('shirttrouserset', '19'),
            ('bodies', '16'), ('topskirtset', '16'), ('jumperleggingsset', '14'), ('bodysuitleggingsset', '13')],
        women=[
            # ('dresses', '11286'),
            ('tshirts', '3497'), ('blouses', '3076'), ('trousers', '2783'),
            ('jackets', '2058'), ('skirts', '1597'), ('shirts', '1564'), ('shorts', '1537'),
            ('jeans', '1451'), ('jumpers', '1448'), ('bikinis', '1406'), ('vests', '1170'),
            ('jumpsuit', '914'), ('leggings', '736'), ('cardigans', '735'), ('coats', '638'),
            ('sweattops', '605'), ('hoodies', '557'), ('socks', '526'), ('coverups', '488'),
            ('joggers', '463'), ('tunics', '428'), ('tanktops', '350'), ('camisoles', '340'),
            ('fleeces', '242'), ('playsuits', '213'), ('bodies', '199'), ('waistcoats', '194'),
            ('gilets', '178'), ('tights', '151'), ('poloshirts', '137'), ('suittrousers', '123'),
            ('tankinis', '97'), ('suitjackets', '84'), ('croptops', '75'), ('ponchos', '46'),
            ('dungarees', '36'), ('boobtube', '35'), ('tracksuits', '28'), ('bodysuits', '25'),
            ('rashvests', '18'), ('allinone', '11'), ('loungewearsets', '11'), ('topshortsets', '10'),
            ('blazers', '6'), ('suitskirts', '2'), ('hoodiejoggerset', '1'), ('jacketshirttrouserset', '1'),
            ('jackettoptrouserset', '1'), ('sweattopjoggersets', '1')]
    )
    base_url_config = dict(
        women="https://www.next.co.uk/shop/gender-women-productaffiliation-clothing/category",
        baby="https://www.next.co.uk/shop/gender-newbornboys-gender-newborngirls-gender-newbornunisex-gender-youngerboys-gender-youngergirls-productaffiliation-clothing/category",
    )
    # TODO 修复 base_url
    r = redis.from_url(settings.redis_dsn, decode_responses=True, protocol=3)

    for gender, subcategories in categories.items():
        for category, count in subcategories:
            async with r:
                key = f"next_category_status:{gender}:{category}"
                result = await r.get(key)
                if result == "done":
                    log.info(f"对 {key} 类别的商品索引已经建立")
                    continue
                else:
                    log.info(f"开始对{key} 类别的商品建立索引")
            print(category, count)
            total = int(count)
            page_size = 12
            page_count = (total + page_size - 1) // page_size
            base_url = "https://www.next.co.uk/shop/gender-women-productaffiliation-clothing/category-hoodies"
            base_url = "https://www.next.co.uk/shop/gender-women-productaffiliation-clothing/category-trousers"
            base_url = "https://www.next.co.uk/shop/gender-women-productaffiliation-clothing/category-jumpers"
            base_url = f"https://www.next.co.uk/shop/gender-women-productaffiliation-clothing/category-{category}"
            base_url = "https://www.next.co.uk/shop/department-homeware-productaffiliation-bedding/"
            base_url = f"https://www.next.co.uk/shop/gender-men-productaffiliation-clothing/category-{category}"
            base_url = f"https://www.next.co.uk/shop/gender-newbornboys-gender-newborngirls-gender-newbornunisex-gender-youngerboys-gender-youngergirls-productaffiliation-clothing/category-{category}"
            # 分段 当页数太多时可能导致chrome内存爆裂

            # base_url = 'https://www.next.co.uk/shop/productaffiliation-gifts/category-pets'
            # base_url = f'https://www.next.co.uk/shop/department-homeware-productaffiliation-bedding/category-{category}'
            base_url = base_url_config.get(gender, "")
            category_url = f"{base_url}-{category}"
            # category = category_url.split("/")[-1].split("-")[-1]
            segment = 40
            times = (page_count + segment - 1) // segment
            print(f"{times=}")
            dresses_not = ["549_600", "825_900"]
            log.debug(f"分页{segment=}, {times=}")
            for j in range(0, times):
                log.debug(f"开始第{j + 1}轮 处理, 共 {times} 轮")
                next_base_url = category_url + f"?p={j * segment + 1}"

                page = await context.new_page()
                async with page:
                    # base_url: str = "https://www.next.co.uk/shop/gender-women-productaffiliation-clothing/category-trousers"
                    # base_url = "https://www.next.co.uk/shop/gender-women-productaffiliation-clothing/category-dresses"
                    a = ["1-50", "50-100", "100-200", "200-326", "326-347", "347"]
                    b = ["1-50", "51-100", "101-200", "200, .."]
                    c = [""]
                    # category = base_url.split("/")[-1].split("-")[-1]
                    print(category)
                    # 拦截所有图片
                    await page.route(
                        "**/*",
                        lambda route: route.abort() if route.request.resource_type == "image" else route.continue_(),
                    )
                    log.debug(f"打开页面: {next_base_url}")
                    await page.goto(next_base_url)
                    b = "/html/body/main/div/div/div[2]/div[4]/div/div[22]/div/div/section/div/div[1]/div[1]/div/div/div[1]/a"
                    selector = "//main/div/div/div[2]/div[4]/div/div/div/div/section/div/div[1]/div[1]/div/div/div[1]/a"
                    li_selector = (
                        "//main/div/div/div[2]/div[4]/div/div/div/div/section/div/div[2]/div[2]/div/div/div/ul/li/a"
                    )
                    await page.wait_for_load_state(timeout=60000)
                    await page.wait_for_timeout(5000)
                    scroll_pause_time = random.randrange(1000, 1800, 200)
                    # await page.wait_for_timeout(1000)
                    log.debug("开始滚动页面")
                    await scroll_page(page, scroll_pause_time=scroll_pause_time, source="next", page_size=segment)
                    # await page.pause()
                    product_locators = page.locator('[data-testid="plp-product-grid-item"]')
                    product_count = await product_locators.count()
                    log.info(f"locators数量: {product_count}")
                    product_urls = []
                    for i in range(product_count):
                        try:
                            url = await product_locators.nth(i).locator(
                                "section > div > div:nth-child(2) > a").get_attribute(
                                "href", timeout=10000)
                            log.debug(f"抓取到商品数量{url}")
                            product_urls.append(url)
                        # TODO 将 所有url 存入redis, 以持久化
                        except Exception as exc:
                            log.error(f"获取商品url失败: {exc}")
                            pass
                    print(f"一共获取商品数: {len(product_urls)}")

                    async with r:
                        # print(await r.get("a"))
                        if product_urls:
                            result = await r.sadd(f"next:{gender}:{category}", *product_urls)
                            print(result)
                        else:
                            log.warning(f"没有获取到商品url: {next_base_url}")
                    # print(products_urls)
                    # 将数据持久化到本地
                    with open(settings.project_dir.joinpath("data", f"{gender}-{category}-next_urls.txt"), "w") as f:
                        for url in product_urls:
                            f.write(url + "\n")
                    print(page.url)
                    # await page.pause()
                    log.debug(f"第{j + 1}轮: {page.url}")
                    await page.wait_for_timeout(2000)
            log.debug(f"完成 对 {category} 类别的商品索引建立")
            async with r:
                await r.set(f"next_category_status:{gender}:{category}", "done")
                log.info(f"完成 对next_category_status:{gender}:{category} 类别的商品索引建立")

    await context.close()


async def main():
    # 创建一个playwright对象并将其传递给run函数
    async with async_playwright() as p:
        await run(p)
        ...


# 这是脚本的入口点。
# 它开始执行main函数。
if __name__ == "__main__":
    # 指定本地代理
    # os.environ["http_proxy"] = "http://127.0.0.1:23457"
    # os.environ["https_proxy"] = "http://127.0.0.1:23457"
    # os.environ["all_proxy"] = "socks5://127.0.0.1:23457"

    asyncio.run(main())
