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

    categories = dict(
        women=[
            ('dresses', '11286'),
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
            ('jackettoptrouserset', '1'), ('sweattopjoggersets', '1')],  # finished
        men=[('tshirts', '3974'), ('shirts', '2741'), ('shorts', '1960'), ('poloshirts', '1729'), ('jackets', '1675'),
             ('trousers', '1191'), ('hoodies', '1119'), ('sweattops', '703'), ('socks', '678'), ('joggers', '629'),
             ('jeans', '620'), ('jumpers', '551'), ('footballshirts', '456'), ('swimshorts', '431'),
             ('suittrousers', '426'), ('suitjackets', '419'), ('fleeces', '254'), ('waistcoats', '240'),
             ('coats', '203'), ('gilets', '192'), ('vests', '162'), ('tracksuits', '81'), ('cardigans', '43'),
             ('rashvests', '36'), ('rugbyshirts', '22'), ('topshortsets', '21'), ('leggings', '15'), ('ponchos', '6'),
             ('allinone', '3'), ('loungewearsets', '3'), ('sweattopjoggersets', '3'), ('tights', '3'),
             ('swimsuits', '2'), ('tanktops', '2'), ('suits', '1')],
        girls=[('dresses', '1548'), ('tshirts', '933'), ('shorts', '397'), ('leggings', '361'), ('jackets', '360'),
               ('sleepsuits', '339'), ('pyjamas', '337'), ('socks', '330'), ('hoodies', '237'), ('skirts', '237'),
               ('trousers', '227'), ('cardigans', '222'), ('sweattops', '207'), ('topshortsets', '194'),
               ('swimsuits', '177'), ('joggers', '174'), ('jeans', '172'), ('bodysuits', '159'), ('coats', '146'),
               ('tights', '125'), ('blouses', '124'), ('briefs', '113'), ('topleggingset', '111'),
               ('rompersuits', '107'), ('playsuits', '93'), ('jumpers', '90'), ('vests', '85'), ('dungarees', '63'),
               ('tracksuits', '63'), ('sunsafesuits', '61'), ('jumpsuit', '60'), ('sweattopleggingset', '54'),
               ('rashvests', '54'), ('sweattopjoggersets', '53'), ('shirts', '49'), ('allinone', '42'), ('bras', '42'),
               ('nighties', '42'), ('poloshirts', '41'), ('robes', '35'), ('puddlesuits', '34'), ('slippers', '31'),
               ('topskirtset', '30'), ('fleeces', '26'), ('dungareeset', '25'), ('ponchos', '25'), ('pramsuits', '25'),
               ('coverups', '22'), ('dressset', '21'), ('sleepsuitset', '19')],
        boys=[('tshirts', '1758'), ('shorts', '740'), ('shirts', '480'), ('jackets', '478'), ('hoodies', '448'),
              ('socks', '445'), ('trousers', '423'), ('poloshirts', '393'), ('pyjamas', '380'), ('joggers', '345'),
              ('swimshorts', '226'), ('jeans', '213'), ('sleepsuits', '172'), ('footballshirts', '168'),
              ('jumpers', '139'), ('bodysuits', '136'), ('coats', '124'), ('topshortsets', '118'),
              ('tracksuits', '103'), ('sweattops', '101'), ('rompersuits', '92'), ('sweattopjoggersets', '88'),
              ('trunks', '86'), ('rashvests', '79'), ('dungarees', '75'), ('cardigans', '67'), ('robes', '59'),
              ('allinone', '57'), ('boxers', '57'), ('fleeces', '53'), ('leggings', '52'), ('gilets', '46'),
              ('suittrousers', '46'), ('briefs', '43'), ('topleggingset', '41'), ('swimsuits', '39'),
              ('sunsafesuits', '38'), ('suitjackets', '37'), ('dungareeset', '36'), ('sweattopshortset', '36'),
              ('vests', '33'), ('puddlesuits', '33'), ('wetsuits', '28'), ('hoodiejoggerset', '22'),
              ('waistcoats', '22'), ('coverups', '21'), ('pramsuits', '19'), ('baselayers', '18'),
              ('sleepsuitset', '18'), ('shirttrouserset', '13')],
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
        gifts=[('pets', 677)],

    )
    base_url_config = dict(
        women="https://www.next.co.uk/shop/gender-women-productaffiliation-clothing/category",
        men="https://www.next.co.uk/shop/gender-men-productaffiliation-clothing/category",
        girls="https://www.next.co.uk/shop/gender-newborngirls-gender-newbornunisex-gender-oldergirls-gender-youngergirls-productaffiliation-girlsclothing/category",
        boys="https://www.next.co.uk/shop/gender-newbornboys-gender-newbornunisex-gender-olderboys-gender-youngerboys-productaffiliation-boysclothing/category",
        baby="https://www.next.co.uk/shop/gender-newbornboys-gender-newborngirls-gender-newbornunisex-gender-youngerboys-gender-youngergirls-productaffiliation-clothing/category",
        gifts="https://www.next.co.uk/shop/productaffiliation-gifts/category",
    )
    # 追加
    categories = dict(
        # women=[('pyjamas', '725')],
        # men=[('pyjamas', '160')],
        # women=[('bras', '2439')],
        women=[
            # ('pyjamas', '737'), 
            ('slippers', '470'), ('nighties', '159'), ('robes', '148'), ('slips', '72'),
            ('camisets', '46'), ('thermals', '42'), ('blankethoodies', '21'), ('socks', '11'), ('hoodies', '10'),
            ('joggers', '7'), ('sweattops', '4'), ('trousers', '4'), ('allinone', '3'), ('topshortsets', '2'),
            ('tracksuits', '2'), ('tshirts', '2'), ('beautysleep', '1'), ('loungewearsets', '1'), ('shorts', '1')],

    )
    base_url_config = dict(
        women="https://www.next.co.uk/shop/gender-women-productaffiliation-nightwear/category",
        # men='https://www.next.co.uk/shop/gender-men-productaffiliation-nightwear/category-pyjamas'
        # women='https://www.next.co.uk/shop/gender-women-productaffiliation-lingerie/category'
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

            base_url = base_url_config.get(gender, "")
            category_url = f"{base_url}-{category}"
            # category = category_url.split("/")[-1].split("-")[-1]
            segment = 40
            times = (page_count + segment - 1) // segment
            print(f"{times=}")
            log.debug(f"分页{segment=}, {times=}")
            for j in range(0, times):
                log.debug(f"开始第{j + 1}轮 处理, 共 {times} 轮")
                next_base_url = category_url + f"?p={j * segment + 1}"

                page = await context.new_page()
                async with page:
                    # category = base_url.split("/")[-1].split("-")[-1]
                    print(category)
                    # 拦截所有图片
                    await page.route(
                        "**/*",
                        lambda route: route.abort() if route.request.resource_type == "image" else route.continue_(),
                    )
                    log.debug(f"打开页面: {next_base_url}")
                    await page.goto(next_base_url)
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
                            log.debug(f"抓取到商品url: {url}")
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
