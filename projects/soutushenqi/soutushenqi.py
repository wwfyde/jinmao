import asyncio
import os
from mimetypes import guess_extension

import httpx
from playwright.async_api import Playwright, async_playwright, Page

from crawler import log
from crawler.config import settings

PLAYWRIGHT_TIMEOUT = settings.playwright.timeout
print(f"{PLAYWRIGHT_TIMEOUT=}")


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
        browser = await chromium.launch(
            headless=True,
            devtools=True,
        )
        context = await browser.new_context()

    # 设置全局超时
    context.set_default_timeout(PLAYWRIGHT_TIMEOUT)
    # 并发打开新的页面

    page = await context.new_page()
    async with page:
        await page.goto("https://www.soutushenqi.com/image/search?searchWord=%E5%88%98%E4%BA%A6%E8%8F%B2")

        await page.get_by_text("自定义尺寸").click()
        await page.get_by_placeholder("最小宽度").click()
        await page.get_by_placeholder("最小宽度").fill("1000")
        await page.get_by_placeholder("最小高度").click()
        await page.get_by_placeholder("最小高度").fill("1000")
        await page.get_by_text("确定").click()
        has_more_content = True
        while has_more_content:
            # await scroll_page(page=page, max_attempt=2)
            await page.wait_for_load_state("domcontentloaded")
            locators = await page.locator('//*[@id="waterfallContainer"]/div[1]/div/div/div').element_handles()
            log.info(f"图片数量：{len(locators)}")
            '//*[@id="waterfallContainer"]/div[1]/div/div/div[8]/div"'
            seen_elements = set()

            for locator in locators:
                if locator not in seen_elements:
                    seen_elements.add(locator)
                    await page.evaluate("element => element.scrollIntoView()", locator)
                    await asyncio.sleep(1)
                    if not await locator.is_visible():
                        log.warning("图片不可见")
                        continue
                    await locator.click()
                    new_page: Page = await context.wait_for_event("page")
                    async with new_page:
                        log.debug("新页面加载中")
                        # await new_page.wait_for_load_state()
                        await new_page.wait_for_timeout(1500)
                        await new_page.wait_for_selector('//*[@id="root"]/div[2]/div/div[1]/div[1]/img')
                        img_locator = new_page.locator('//*[@id="root"]/div[2]/div/div[1]/div[1]/img')
                        image_url = await img_locator.get_attribute("src")
                        log.debug(f"{image_url=}")
                        if not image_url:
                            continue
                        try:
                            async with httpx.AsyncClient() as client:
                                response = await client.get(image_url, timeout=settings.httpx_timeout)
                                response.raise_for_status()

                                image_basename = f"image_{image_url.split('/')[-1]}"
                                content_type = response.headers.get("Content-Type", "")
                                if content_type.startswith("image"):
                                    image_basename = image_basename.split(".")[0]
                                    exstension = guess_extension(content_type)
                                image_name = (
                                    image_basename
                                    if image_basename.endswith(exstension)
                                    else image_basename + exstension
                                )

                                store_path = settings.cong_dir.joinpath("liuyifei")
                                store_path.mkdir(parents=True, exist_ok=True)
                                image_path = str(store_path.joinpath(image_name))
                                print(f"{image_path=}")
                                with open(image_path, "wb") as f:
                                    log.debug(f"开始下载图片：{image_url}")
                                    log.info(f"图片保存路径：{image_url}")
                                    f.write(response.content)
                                    log.info("图片保存成功")
                                    # 判断写入的文件是否存在
                                    if not image_path.exists():
                                        log.error("下载图片失败")
                                    else:
                                        # 通过mac open 命令打开图片
                                        os.system(f"open {image_path}")
                        except Exception as exc:
                            log.error(f"下载图片失败：{exc}")
                    await asyncio.sleep(1)
                log.info("新页面加载完成")

                # await page.pause()

            previous_height = await page.evaluate("document.body.scrollHeight")
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(2)  # 等待页面加载新内容
            current_height = await page.evaluate("document.body.scrollHeight")

            # 检查是否加载了新内容
            has_more_content = current_height > previous_height

        # await page.pause()
    await context.close()


async def main():
    async with async_playwright() as p:
        await run(p)


if __name__ == "__main__":
    asyncio.run(main())
