import asyncio

from playwright.async_api import async_playwright, Playwright

from crawler.config import settings
from crawler.deps import get_logger

log = get_logger("next")
log.info(f"日志配置成功, 日志器: {log.name}")


async def run(playwright: Playwright) -> None:
    # 从playwright对象中获取chromium浏览器
    chromium = playwright.chromium
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
            headless=settings.playwright.headless,
            proxy=proxy,
            # headless=False,
            # slow_mo=50,  # 每个操作的延迟时间（毫秒），便于调试
            # args=["--start-maximized"],  # 启动时最大化窗口
            # ignore_https_errors=True,  # 忽略HTTPS错误
            # devtools=True,
        )
    else:
        browser = await chromium.launch(
            headless=settings.playwright.headless,
            devtools=True,
            proxy=proxy,
        )
        context = await browser.new_context()

    # 设置全局超时
    context.set_default_timeout(60 * 1000)

    page = await context.new_page()
    async with page:
        await page.goto("https://www.next.co.uk/style/su262440/n89657#n89657")
        await page.wait_for_load_state("domcontentloaded")

        image_locators = await page.locator(
            "#ZoomComponent > div.shotmedia > div > div.ThumbNailNavClip > ul > li > a > img"
        ).element_handles()
        model_image_urls = []
        for image_locator in image_locators:
            image_url = await image_locator.get_attribute("src")
            model_image_urls.append(image_url)
            log.info(f"获取到图片链接: {image_url}")
        await page.pause()


async def main():
    async with async_playwright() as p:
        await run(p)


if __name__ == "__main__":
    asyncio.run(main())
