import asyncio

from playwright.async_api import Playwright, async_playwright

from crawler import log
from crawler.config import settings
from projects.target.target_category_concurrency import open_pdp_page

PLAYWRIGHT_TIMEOUT = settings.playwright.timeout
PLAYWRIGHT_TIMEOUT = 1000 * 30
__doc__ = """
示例单品 A-90021837
https://www.target.com/p/women-s-shrunken-short-sleeve-t-shirt-universal-thread/-/A-90021837#lnk=sametab
"""
log.debug(f"默认超时时间: {PLAYWRIGHT_TIMEOUT}")


async def run(playwright: Playwright) -> None:
    # 从playwright对象中获取chromium浏览器
    chromium = playwright.chromium
    user_data_dir = settings.user_data_dir
    if settings.save_login_state:
        context = await playwright.chromium.launch_persistent_context(
            user_data_dir,
            headless=False,
            # headless=False,
            # slow_mo=50,  # 每个操作的延迟时间（毫秒），便于调试
            # args=["--start-maximized"],  # 启动时最大化窗口
            # ignore_https_errors=True,  # 忽略HTTPS错误
            # devtools=True,
        )
    else:
        pass
    browser = await chromium.launch(
        headless=settings.playwright.headless,
        # devtools=True,
    )
    semaphore = asyncio.Semaphore(5)
    # TODO  修改如下参数
    main_category = "pets"
    sub_category = "cat-treats"
    # base_url: str = "https://www.target.com/p/women-s-tie-waist-button-front-midi-skirt-universal-thread/-/A-89766757"
    #
    # base_url: str = "https://www.target.com/p/women-s-poplin-cross-back-dress-a-new-day/-/A-90587245"
    url = "https://www.target.com/p/women-s-strapless-midi-sweater-dress-universal-thread/-/A-90176248?preselect=90002352#lnk=sametab"
    url = "https://www.target.com/p/women-s-poplin-cross-back-dress-a-new-day/-/A-90587245?preselect=90564226"
    # url = "https://www.target.com/p/women-s-poplin-cross-back-dress-a-new-day/-/A-90587245?preselect=90564228"
    url = "https://www.target.com/p/women-s-poplin-cross-back-dress-a-new-day/-/A-90587245?preselect=90564236"
    url = "https://www.target.com/p/allegra-k-women-s-glitter-sequin-spaghetti-strap-v-neck-party-cocktail-sparkly-mini-dress/-/A-87419082?preselect=89041542#lnk=sametab"
    url = "https://www.target.com/p/women-s-best-ever-maxi-a-line-dress-a-new-day/-/A-90368246?preselect=90379157#lnk=sametab"
    url = "https://www.target.com/p/women-s-flutter-cap-sleeve-maxi-a-line-dress-universal-thread/-/A-91637488?preselect=91485713#lnk=sametab"
    url = "https://www.target.com/p/greenies-petite-original-chicken-adult-dental-dog-treats/-/A-54557364?preselect=75666634"
    url = "https://www.target.com/p/hartz-delectables-sqeeze-up-chicken-38-tuna-cat-treats-variety-pack-5oz-10ct/-/A-80783370?preselect=80783370"
    sku_tasks = [
        ("pets", "cat-treats",
         "https://www.target.com/p/hartz-delectables-sqeeze-up-chicken-38-tuna-cat-treats-variety-pack-5oz-10ct/-/A-80783370?preselect=80783370"),
        ("pets", "dog-treats",
         "https://www.target.com/p/greenies-petite-original-chicken-adult-dental-dog-treats/-/A-54557364?preselect=75666634"),
        ("pets", "cat-treats",
         "https://www.target.com/p/delectables-hartz-squeeze-up-chicken-flavored-cat-treat-2oz-4ct/-/A-76375257?preselect=76375257"),
    ]
    for (main_category, sub_category, url) in sku_tasks:
        await open_pdp_page(
            browser,
            url=url,
            semaphore=semaphore,
            source="target",
            main_category=main_category,
            sub_category=sub_category,
        )
    # TODO 暂不关闭浏览器
    await browser.close()


async def main():
    # 创建一个playwright对象并将其传递给run函数
    async with async_playwright() as p:
        await run(p)
        ...


# 这是脚本的入口点。
# 它开始执行main函数。
if __name__ == "__main__":
    # 指定代理
    # os.environ["http_proxy"] = "http://127.0.0.1:23457"
    # os.environ["https_proxy"] = "http://127.0.0.1:23457"
    # os.environ["all_proxy"] = "socks5://127.0.0.1:23457"
    asyncio.run(main(), debug=True)
