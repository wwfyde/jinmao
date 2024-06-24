import asyncio

from playwright.async_api import Playwright, async_playwright

from crawler import log
from crawler.config import settings
from projects.target.target_category import open_pdp_page

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
        browser = await chromium.launch(headless=True, devtools=True)
        context = await browser.new_context()

    # browser = await chromium.launch(headless=True)
    # context = await browser.new_context()

    # 设置全局超时
    context.set_default_timeout(PLAYWRIGHT_TIMEOUT)
    # 创建一个新的浏览器上下文，设置视口大小
    # context = await browser.new_context(viewport={"width": 1920, "height": 1080})
    # 在浏览器上下文中打开一个新页面
    base_url: str = "https://www.target.com/p/women-s-tie-waist-button-front-midi-skirt-universal-thread/-/A-89766757"
    base_url: str = "https://www.target.com/p/women-s-poplin-cross-back-dress-a-new-day/-/A-90587245"
    # 关闭浏览器context
    await open_pdp_page(context, url=base_url)
    # TODO 暂不关闭浏览器
    await context.close()


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
