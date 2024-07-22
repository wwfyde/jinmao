import asyncio
import logging

import redis.asyncio as redis
from playwright.async_api import Playwright, async_playwright

from crawler.config import settings

PLAYWRIGHT_TIMEOUT: int = settings.playwright.timeout or 1000 * 60
print(PLAYWRIGHT_TIMEOUT)
PLAYWRIGHT_CONCURRENCY: int = settings.playwright.concurrency or 10
PLAYWRIGHT_CONCURRENCY: int = 8
PLAYWRIGHT_HEADLESS: bool = settings.playwright.headless
PLAYWRIGHT_HEADLESS = False


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
        browser = await chromium.launch(headless=PLAYWRIGHT_HEADLESS, proxy=proxy)
        context = await browser.new_context()

    # 设置全局超时
    context.set_default_timeout(settings.playwright.timeout)
    """
    客户款号GAP款号.xlsx
    """
    styles = []
    style_ids_sum24_women = [  # women
        793269,
        623795,
        881150,
        885499,
        881157,
        885498,

        431194,
        431249,
        431270,
        431230,
        431253,
        767285,
        767303,
        810231,

        663802,
        663803,
        709290,
        860852,
        490772,
        587820,
        767408,
        767408,
        431248,
        431256,
        431268,
        407881,
        407882,
        407884,
        670516,
        739113,
        409771,
        409769,

    ]
    styles.extend([(item, 'women') for item in style_ids_sum24_women])
    style_ids_sum24_men = [
        401672,
        606506,
        735795,
        885502,
        608891,
        496861,
        608930,
        606484,
        878160,
        446216,
        370404,
        370407,
        372200,
        618357,
        790798,
        796309,
    ]
    styles.extend([(item, 'men') for item in style_ids_sum24_men])
    style_ids_sum24_boys = [
        407828,
        407852,
        432724,
        432755,
        432732,
        432726,
        432730,
        432685,
        432715,
        881856,
        437589,
        404639,
        437792,
        404649,
        437580,
        404622,
        446230,
    ]
    styles.extend([(item, 'boys') for item in style_ids_sum24_boys])
    style_ids_sum24_girls = [
        432481,
        432484,
        432489,
        432479,
        432497,
        407965,

        435032,
        446218,
        805041,
        858412,
    ]
    styles.extend([(item, 'girls') for item in style_ids_sum24_girls])
    style_ids_sum24_baby_girls = [407815, ]
    styles.extend([(item, 'baby_girls') for item in style_ids_sum24_baby_girls])
    style_ids = [  # women
        793269,
        623795,
        623795,
        830494,
        881150,
        885499,
        881157,
        885498,
        885498,
        767285,
        767303,
        810231,
        681602,
        663802,
        663803,
        860852,
        709290,
        490772,
        587820,
        767408,
        739113,
        754457,
    ]
    styles.extend([(item, 'women') for item in style_ids])
    style_ids = [  # men
        401672,
        735795,
        885502,
        606506,
        736484,
        608891,
        608930,
        606484,
        878160,
        885500,
        602577,
        370404,
        370407,
        372200,
        540888,
        618357,
        790798,
        796309,
        891754,
    ]
    styles.extend([(item, 'men') for item in style_ids])
    style_ids = [  # boys
        838218,
        874579,
        879147,
        874583,
        870729,
        879170,
        879169,
        879160,
        879171,
        879129,
        881888,
        868245,
        881856,
        868288,
        881832,
        868273,
        805040,
    ]
    styles.extend([(item, 'boys') for item in style_ids])

    style_ids = [
        838237,
        870731,
        879063,
        879078,
        879075,
        878911,
        879029,
        878916,
        879002,
        876422,
        868380,
        876415,
        868367,
        876418,
        886039,
        805041,
    ]  # girls
    styles.extend([(item, 'girls') for item in style_ids])
    style_ids = [805044, 879282, 879319, 879201]  # baby_girls
    styles.extend([(item, 'baby_girls') for item in style_ids])

    style_ids = [879263, 879218]  # baby_boys
    styles.extend([(item, 'baby_boys') for item in style_ids])
    print(styles, len(styles))
    for style_id, gender in styles:
        page = await context.new_page()
        async with page:
            await page.route(
                "**/*",
                lambda route: route.abort() if route.request.resource_type == "image" else route.continue_(),
            )
            await page.goto(f"https://www.gap.com/browse/search.do?searchText={style_id}")
            await page.wait_for_load_state()
            if "browse/product.do" in page.url:
                print("yes")
                # 将商品索引加入到redis
                r = redis.from_url(settings.redis_dsn, decode_responses=True, protocol=3)
                async with r:
                    await r.set(f"gap_search:{gender}:{style_id}", page.url)
                    logging.info(f"将商品{style_id}索引加入到redis")

            else:
                print(f"款号{style_id}未搜索到")

            # await page.pause()


async def main():
    # 创建一个playwright对象并将其传递给run函数
    async with async_playwright() as p:
        await run(p)
        ...


if __name__ == "__main__":
    asyncio.run(main())
