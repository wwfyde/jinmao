import asyncio

from playwright.async_api import async_playwright, Playwright


# 这个函数负责启动一个浏览器，打开一个新页面，并在页面上执行操作。
# 它接受一个Playwright对象作为参数。
async def run(playwright: Playwright) -> None:
    # 从playwright对象中获取chromium浏览器
    chromium = playwright.chromium
    # 启动chromium浏览器，开启开发者工具，非无头模式
    browser = await chromium.launch(headless=False, devtools=True)
    # 创建一个新的浏览器上下文，设置视口大小
    context = await browser.new_context(viewport={"width": 1920, "height": 1080})
    # 在浏览器上下文中打开一个新页面
    page = await context.new_page()
    # 导航到指定的URL
    await page.goto("https://www.baidu.com")
    # 其他操作...
    # 暂停执行
    await page.pause()  # 暂停以允许手动继续
    # 对当前页面进行截图，并保存到指定路径
    await page.screenshot(path="example.png", type="png", full_page=True)
    # 关闭浏览器
    await browser.close()


# 这个函数是脚本的主入口点。
# 它创建一个playwright对象，并将其传递给run函数。
async def main():
    # 创建一个playwright对象并将其传递给run函数
    async with async_playwright() as p:
        await run(p)
        ...


# 这是脚本的入口点。
# 它开始执行main函数。
if __name__ == "__main__":
    asyncio.run(main(), debug=True)
